# worker/motionanchor_worker/worker.py
"""MotionAnchor Protocol 1.0 worker main loop.

Reads NDJSON from *stdin*, writes NDJSON to *stdout*, and sends
diagnostic messages to *stderr*.  The loop is intentionally simple:
no threads, no asyncio — just blocking reads so the Rust host can
drive the lifecycle deterministically.

Entry point: ``run_loop(stdin, stdout, stderr)`` or the ``__main__``
script.
"""

from __future__ import annotations

import sys
from dataclasses import asdict
from typing import IO, Optional

from . import PROTOCOL_VERSION
from .errors import WorkerError, internal, unknown_type
from .jobs import JobNotFoundError
from .jobs.media import MediaJobService
from .segmentation import (
    Sam2ProcessError,
    build_sam2_bootstrap_plan,
    probe_sam2_runtime,
    write_sam2_bootstrap_script,
)
from .media.ffmpeg import FfmpegAdapter
from .media.handlers import (
    AdapterFactory,
    MediaRequestError,
    MediaToolError,
    execute_media_request,
)
from .protocol import (
    TYPE_ERROR,
    TYPE_JOB_CANCEL,
    TYPE_JOB_STATUS,
    TYPE_JOB_SUBMIT_EXTRACT_FRAMES,
    TYPE_JOB_SUBMIT_MOTION_SELECTION,
    TYPE_JOB_SUBMIT_SEGMENT_RGBA,
    TYPE_JOB_SUBMIT_SAM2_BOOTSTRAP,
    TYPE_MEDIA_EXTRACT_FRAMES,
    TYPE_MEDIA_PROBE,
    TYPE_SEGMENTATION_SAM2_BOOTSTRAP_PLAN,
    TYPE_SEGMENTATION_SAM2_BOOTSTRAP_WRITE,
    TYPE_SEGMENTATION_SAM2_PREFLIGHT,
    TYPE_WORKER_PING,
    TYPE_WORKER_PONG,
    TYPE_WORKER_READY,
    TYPE_WORKER_SHUTDOWN,
    TYPE_WORKER_STARTUP,
    TYPE_WORKER_STOPPED,
    envelope_to_json,
    make_envelope,
    make_error_envelope,
    new_message_id,
    parse_line,
    validate_envelope,
)


def _diag(stderr: IO[str], text: str) -> None:
    """Write a single diagnostic line to stderr."""
    stderr.write(text)
    stderr.write("\n")
    stderr.flush()


def _write(stdout: IO[bytes], env: dict) -> None:
    """Serialize and write an envelope to stdout."""
    stdout.write(envelope_to_json(env))
    stdout.flush()


def _send_startup(stdout: IO[bytes], stderr: IO[str]) -> None:
    """Emit the initial ``worker.ready`` handshake envelope."""
    env = make_envelope(
        message_type=TYPE_WORKER_READY,
        payload={
            "protocol_version": PROTOCOL_VERSION,
            "worker_id": new_message_id(),
        },
    )
    _write(stdout, env)
    _diag(stderr, "[motionanchor] worker handshake sent")


def _handle_ping(
    obj: dict,
    stdout: IO[bytes],
    stderr: IO[str],
) -> None:
    """Reply to a ``worker.ping`` preserving the caller's ``message_id``."""
    original_id = obj.get("message_id", "")
    _diag(stderr, f"[motionanchor] ping received (id={original_id})")
    pong = make_envelope(
        message_type=TYPE_WORKER_PONG,
        payload={},
        message_id=original_id,
    )
    _write(stdout, pong)


def _handle_unknown(
    obj: dict,
    stdout: IO[bytes],
    stderr: IO[str],
) -> bool:
    """Send a structured ``unknown_type`` error.  Returns True to continue."""
    msg_type = obj.get("type")
    _diag(stderr, f"[motionanchor] unknown type: {msg_type}")
    err = unknown_type(msg_type)
    err_env = make_error_envelope(
        err,
        in_reply_to=obj.get("message_id"),
        job_id=obj.get("job_id"),
    )
    _write(stdout, err_env)
    return True


def run_loop(
    stdin: IO[str],
    stdout: IO[bytes],
    stderr: IO[str],
    adapter_factory: Optional[AdapterFactory] = None,
    media_jobs: Optional[MediaJobService] = None,
) -> int:
    """Run the worker event loop until EOF or ``worker.shutdown``.

    Returns an integer exit code suitable for ``sys.exit``.
    """
    _send_startup(stdout, stderr)
    jobs = media_jobs or MediaJobService(adapter_factory=adapter_factory or FfmpegAdapter)

    running = True

    while running:
        raw_line = stdin.readline()

        # EOF — host closed the pipe
        if raw_line == "":
            _diag(stderr, "[motionanchor] stdin EOF, shutting down")
            break

        obj, err = parse_line(raw_line.encode("utf-8"))

        # Blank / whitespace-only line — skip
        if obj is None and err is None:
            continue

        # Malformed bytes that did not parse as JSON
        if err is not None:
            _diag(stderr, f"[motionanchor] parse error: {err.message}")
            err_env = make_error_envelope(err)
            _write(stdout, err_env)
            continue

        assert obj is not None  # for type checkers

        val_err = validate_envelope(obj)
        if val_err is not None:
            _diag(stderr, f"[motionanchor] envelope error: {val_err.message}")
            err_env = make_error_envelope(
                val_err,
                in_reply_to=obj.get("message_id"),
                job_id=obj.get("job_id"),
            )
            _write(stdout, err_env)
            continue

        msg_type = obj.get("type")

        # ── well-known types ────────────────────────────────────────

        if msg_type == TYPE_WORKER_STARTUP:
            _diag(stderr, "[motionanchor] handshake acknowledged")
            continue

        if msg_type == TYPE_WORKER_PING:
            _handle_ping(obj, stdout, stderr)
            continue

        if msg_type == TYPE_SEGMENTATION_SAM2_PREFLIGHT:
            try:
                _write(stdout, make_envelope(
                    message_type="segmentation.sam2_preflight_result",
                    message_id=obj.get("message_id"),
                    payload=probe_sam2_runtime(),
                ))
            except Sam2ProcessError as exc:
                _write(stdout, make_error_envelope(
                    WorkerError(code="sam2_preflight_failed", message=str(exc)),
                    in_reply_to=obj.get("message_id"),
                ))
            continue

        if msg_type == TYPE_SEGMENTATION_SAM2_BOOTSTRAP_PLAN:
            payload = obj["payload"]
            script_path = payload.get("script_path")
            if script_path is not None and not isinstance(script_path, str):
                _write(stdout, make_error_envelope(
                    WorkerError(code="invalid_request", message="payload.script_path must be a string"),
                    in_reply_to=obj.get("message_id"),
                ))
                continue
            plan = build_sam2_bootstrap_plan(script_path)
            _write(stdout, make_envelope(
                message_type="segmentation.sam2_bootstrap_plan_result",
                message_id=obj.get("message_id"),
                payload=asdict(plan),
            ))
            continue

        if msg_type == TYPE_SEGMENTATION_SAM2_BOOTSTRAP_WRITE:
            try:
                script_path = obj["payload"].get("script_path")
                if not isinstance(script_path, str) or not script_path.strip():
                    raise ValueError("payload.script_path must be a non-empty string")
                result = write_sam2_bootstrap_script(script_path)
                _write(stdout, make_envelope(
                    message_type="segmentation.sam2_bootstrap_write_result",
                    message_id=obj.get("message_id"),
                    payload=result,
                ))
            except ValueError as exc:
                _write(stdout, make_error_envelope(
                    WorkerError(code="sam2_bootstrap_blocked", message=str(exc)),
                    in_reply_to=obj.get("message_id"),
                ))
            continue

        if msg_type == TYPE_JOB_SUBMIT_EXTRACT_FRAMES:
            try:
                payload = obj["payload"]
                source = payload.get("source_path")
                output = payload.get("output_path")
                if not isinstance(source, str) or not source.strip():
                    raise MediaRequestError("payload.source_path must be a non-empty string")
                if not isinstance(output, str) or not output.strip():
                    raise MediaRequestError("payload.output_path must be a non-empty string")
                job_id = jobs.submit_extract_frames(source, output)
                _write(stdout, make_envelope(
                    message_type="job.accepted",
                    message_id=obj.get("message_id"),
                    job_id=job_id,
                    payload={"job_id": job_id, "operation": "media.extract_frames"},
                ))
            except MediaRequestError as exc:
                _write(stdout, make_error_envelope(
                    WorkerError(code="invalid_request", message=str(exc)),
                    in_reply_to=obj.get("message_id"),
                ))
            continue


        if msg_type == TYPE_JOB_SUBMIT_MOTION_SELECTION:
            try:
                payload = obj["payload"]
                frames = payload.get("frames_path")
                output = payload.get("output_path")
                if not isinstance(frames, str) or not frames.strip():
                    raise MediaRequestError("payload.frames_path must be a non-empty string")
                if not isinstance(output, str) or not output.strip():
                    raise MediaRequestError("payload.output_path must be a non-empty string")
                job_id = jobs.submit_motion_selection(
                    frames,
                    output,
                    max_frames=payload.get("max_frames", 48),
                    preview_width=payload.get("preview_width", 192),
                    uniform_fraction=payload.get("uniform_fraction", 0.5),
                )
                _write(stdout, make_envelope(
                    message_type="job.accepted",
                    message_id=obj.get("message_id"),
                    job_id=job_id,
                    payload={"job_id": job_id, "operation": "media.select_motion_frames"},
                ))
            except (MediaRequestError, ValueError, TypeError) as exc:
                _write(stdout, make_error_envelope(
                    WorkerError(code="invalid_request", message=str(exc)),
                    in_reply_to=obj.get("message_id"),
                ))
            continue


        if msg_type == TYPE_JOB_SUBMIT_SAM2_BOOTSTRAP:
            try:
                script_path = obj["payload"].get("script_path")
                if not isinstance(script_path, str) or not script_path.strip():
                    raise MediaRequestError("payload.script_path must be a non-empty string")
                job_id = jobs.submit_sam2_bootstrap(script_path)
                _write(stdout, make_envelope(
                    message_type="job.accepted",
                    message_id=obj.get("message_id"),
                    job_id=job_id,
                    payload={"job_id": job_id, "operation": "segmentation.sam2_bootstrap"},
                ))
            except MediaRequestError as exc:
                _write(stdout, make_error_envelope(
                    WorkerError(code="invalid_request", message=str(exc)),
                    in_reply_to=obj.get("message_id"),
                ))
            continue

        if msg_type == TYPE_JOB_SUBMIT_SEGMENT_RGBA:
            try:
                payload = obj["payload"]
                frames = payload.get("frames_path")
                output = payload.get("output_path")
                prompt = payload.get("prompt_path")
                if not isinstance(frames, str) or not frames.strip():
                    raise MediaRequestError("payload.frames_path must be a non-empty string")
                if not isinstance(output, str) or not output.strip():
                    raise MediaRequestError("payload.output_path must be a non-empty string")
                if not isinstance(prompt, str) or not prompt.strip():
                    raise MediaRequestError("payload.prompt_path must be a non-empty string")
                job_id = jobs.submit_sam2_rgba(
                    frames,
                    output,
                    prompt,
                    model=payload.get("model", "small"),
                    feather_radius=payload.get("feather_radius", 1.5),
                    defringe=payload.get("defringe", True),
                )
                _write(stdout, make_envelope(
                    message_type="job.accepted",
                    message_id=obj.get("message_id"),
                    job_id=job_id,
                    payload={"job_id": job_id, "operation": "segmentation.sam2_rgba"},
                ))
            except (MediaRequestError, ValueError) as exc:
                _write(stdout, make_error_envelope(
                    WorkerError(code="invalid_request", message=str(exc)),
                    in_reply_to=obj.get("message_id"),
                ))
            continue

        if msg_type in {TYPE_JOB_STATUS, TYPE_JOB_CANCEL}:
            job_id = obj.get("job_id") or obj["payload"].get("job_id")
            if not isinstance(job_id, str) or not job_id:
                _write(stdout, make_error_envelope(
                    WorkerError(code="invalid_request", message="job_id is required"),
                    in_reply_to=obj.get("message_id"),
                ))
                continue
            try:
                if msg_type == TYPE_JOB_STATUS:
                    payload = jobs.status(job_id)
                    response_type = "job.status_result"
                else:
                    payload = {"job_id": job_id, "accepted": jobs.cancel(job_id)}
                    response_type = "job.cancel_result"
                _write(stdout, make_envelope(
                    message_type=response_type,
                    message_id=obj.get("message_id"),
                    job_id=job_id,
                    payload=payload,
                ))
            except JobNotFoundError:
                _write(stdout, make_error_envelope(
                    WorkerError(code="job_not_found", message="unknown job_id"),
                    in_reply_to=obj.get("message_id"),
                    job_id=job_id,
                ))
            continue

        if msg_type in {TYPE_MEDIA_PROBE, TYPE_MEDIA_EXTRACT_FRAMES}:
            try:
                response_type, payload = execute_media_request(
                    msg_type,
                    obj["payload"],
                    adapter_factory or FfmpegAdapter,
                )
                _write(stdout, make_envelope(
                    message_type=response_type,
                    message_id=obj.get("message_id"),
                    job_id=obj.get("job_id"),
                    payload=payload,
                ))
            except MediaRequestError as exc:
                _write(stdout, make_error_envelope(
                    WorkerError(code="invalid_request", message=str(exc)),
                    in_reply_to=obj.get("message_id"),
                    job_id=obj.get("job_id"),
                ))
            except MediaToolError as exc:
                _write(stdout, make_error_envelope(
                    WorkerError(code="media_tool_error", message=str(exc)),
                    in_reply_to=obj.get("message_id"),
                    job_id=obj.get("job_id"),
                ))
            except Exception as exc:
                _diag(stderr, f"[motionanchor] media request failed: {type(exc).__name__}")
                _write(stdout, make_error_envelope(
                    internal("media operation failed"),
                    in_reply_to=obj.get("message_id"),
                    job_id=obj.get("job_id"),
                ))
            continue

        if msg_type == TYPE_WORKER_SHUTDOWN:
            _diag(stderr, "[motionanchor] shutdown requested")
            env = make_envelope(
                message_type=TYPE_WORKER_STOPPED,
                message_id=obj.get("message_id"),
                payload={},
            )
            _write(stdout, env)
            running = False
            continue

        # ── fallback ────────────────────────────────────────────────
        _handle_unknown(obj, stdout, stderr)

    _diag(stderr, "[motionanchor] worker loop exited")
    return 0


def main() -> None:
    """Entry point for ``python -m motionanchor_worker``."""
    code = run_loop(sys.stdin, sys.stdout.buffer, sys.stderr)
    sys.exit(code)
