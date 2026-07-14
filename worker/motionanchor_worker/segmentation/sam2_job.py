# worker/motionanchor_worker/segmentation/sam2_job.py
"""Supervise the isolated SAM 2 process from the production worker.

The main worker does not import PyTorch or SAM 2. It validates paths and
settings, launches the pinned Python 3.12 environment, streams progress,
and publishes output only after the child process completes successfully.
"""

from __future__ import annotations

import json
import os
from collections import deque
import shutil
import subprocess
import tempfile
from pathlib import Path
from threading import Thread
from typing import Any, Callable

Progress = Callable[[float, str | None], None]
Cancelled = Callable[[], bool]


class Sam2RequestError(ValueError):
    """Raised when a SAM 2 job request violates the production contract."""


class Sam2ProcessError(RuntimeError):
    """Raised when the isolated SAM 2 process cannot complete safely."""


def _required_directory(raw: str, field: str, *, must_exist: bool) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise Sam2RequestError(f"{field} must be a non-empty string")
    path = Path(raw).expanduser()
    if must_exist and not path.is_dir():
        raise Sam2RequestError(f"{field} must reference an existing directory")
    return path


def _required_file(raw: str, field: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise Sam2RequestError(f"{field} must be a non-empty string")
    path = Path(raw).expanduser()
    if not path.is_file():
        raise Sam2RequestError(f"{field} must reference an existing file")
    return path


def _prepare_output(raw: str) -> Path:
    output = _required_directory(raw, "output_path", must_exist=False)
    if output.exists():
        if not output.is_dir():
            raise Sam2RequestError("output_path must be a directory")
        if any(output.iterdir()):
            raise Sam2RequestError("output_path must be empty")
    if not output.parent.is_dir():
        raise Sam2RequestError("output_path parent must exist")
    return output


def _resolve_python() -> Path:
    configured = os.environ.get("MOTIONANCHOR_SAM2_PYTHON")
    path = Path(configured).expanduser() if configured else (
        Path(__file__).resolve().parents[2] / ".venv-sam2" / "Scripts" / "python.exe"
    )
    if not path.is_file():
        raise Sam2ProcessError("SAM 2 Python environment is unavailable")
    return path


def _resolve_runner() -> Path:
    configured = os.environ.get("MOTIONANCHOR_SAM2_RUNNER")
    path = Path(configured).expanduser() if configured else Path(__file__).with_name("sam2_process.py")
    if not path.is_file():
        raise Sam2ProcessError("SAM 2 process runner is unavailable")
    return path



def probe_sam2_runtime() -> dict[str, Any]:
    """Return a complete dependency and hardware readiness report."""

    python = _resolve_python()
    runner = _resolve_runner()
    checkpoint = Path(__file__).resolve().parents[2] / "models" / "sam2" / "sam2.1_hiera_small.pt"
    script = r"""
import hashlib
import importlib
import json
import platform
import sys
from pathlib import Path

result = {
    "python": sys.executable,
    "python_version": platform.python_version(),
    "packages": {},
}
for module_name, distribution_name in (
    ("numpy", "numpy"),
    ("cv2", "opencv-python-headless"),
    ("torch", "torch"),
    ("sam2", "sam2"),
):
    try:
        module = importlib.import_module(module_name)
        result["packages"][module_name] = {
            "available": True,
            "version": getattr(module, "__version__", None),
            "distribution": distribution_name,
            "error": None,
        }
    except Exception as exc:
        result["packages"][module_name] = {
            "available": False,
            "version": None,
            "distribution": distribution_name,
            "error": str(exc),
        }

try:
    import torch
    result.update({
        "torch_available": True,
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
    })
    if torch.cuda.is_available():
        properties = torch.cuda.get_device_properties(0)
        result.update({
            "gpu": torch.cuda.get_device_name(0),
            "vram_bytes": properties.total_memory,
            "cuda_version": torch.version.cuda,
        })
except Exception as exc:
    result.update({
        "torch_available": False,
        "torch_version": None,
        "cuda_available": False,
        "error": str(exc),
    })

checkpoint = Path(sys.argv[1])
result["checkpoint_exists"] = checkpoint.is_file()
result["checkpoint_sha256"] = (
    hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if checkpoint.is_file()
    else None
)
print(json.dumps(result))
"""
    completed = subprocess.run(
        [str(python), "-c", script, str(checkpoint)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise Sam2ProcessError(completed.stderr.strip() or "SAM 2 preflight failed")
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise Sam2ProcessError("SAM 2 preflight emitted invalid JSON") from exc

    expected = "6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38"
    packages = report.get("packages") if isinstance(report.get("packages"), dict) else {}
    missing_components = [
        name for name in ("numpy", "cv2", "torch", "sam2")
        if not isinstance(packages.get(name), dict) or not packages[name].get("available")
    ]
    python_version = str(report.get("python_version") or "")
    report["python_compatible"] = python_version.startswith("3.12.")
    report["runner"] = str(runner.resolve())
    report["runner_exists"] = runner.is_file()
    report["checkpoint_valid"] = report.get("checkpoint_sha256") == expected
    report["missing_components"] = missing_components
    readiness_errors: list[str] = []
    if not report["python_compatible"]:
        readiness_errors.append("SAM 2 requires the pinned Python 3.12 runtime")
    if missing_components:
        readiness_errors.append("Missing runtime packages: " + ", ".join(missing_components))
    if not report.get("cuda_available"):
        readiness_errors.append("CUDA is unavailable in the SAM 2 runtime")
    if not report["checkpoint_valid"]:
        readiness_errors.append("SAM 2 checkpoint is missing or invalid")
    if not report["runner_exists"]:
        readiness_errors.append("SAM 2 process runner is unavailable")
    report["readiness_errors"] = readiness_errors
    report["ready"] = not readiness_errors
    report["error"] = readiness_errors[0] if readiness_errors else None
    return report


def _require_sam2_runtime() -> None:
    """Block production execution when the isolated runtime is incomplete."""

    if os.environ.get("MOTIONANCHOR_SAM2_RUNNER"):
        return
    runtime = probe_sam2_runtime()
    if not runtime["ready"]:
        details = "; ".join(runtime.get("readiness_errors") or ["SAM 2 runtime is not ready"])
        raise Sam2ProcessError(details)

def run_sam2_rgba_job(
    *,
    frames_path: str,
    output_path: str,
    prompt_path: str,
    model: str,
    feather_radius: float,
    defringe: bool,
    report: Progress,
    cancelled: Cancelled,
) -> dict[str, Any]:
    """Run SAM 2 in an isolated process and atomically publish its artifacts."""

    _require_sam2_runtime()
    frames = _required_directory(frames_path, "frames_path", must_exist=True).resolve()
    output = _prepare_output(output_path)
    prompt = _required_file(prompt_path, "prompt_path").resolve()
    if model != "small":
        raise Sam2RequestError("model must be 'small'")
    if not isinstance(feather_radius, (int, float)) or not 0 <= float(feather_radius) <= 8:
        raise Sam2RequestError("feather_radius must be between 0 and 8")
    if not isinstance(defringe, bool):
        raise Sam2RequestError("defringe must be a boolean")

    temp_root = Path(tempfile.mkdtemp(prefix=f".{output.name}-sam2-", dir=output.parent.resolve()))
    request_path = temp_root / "request.json"
    process: subprocess.Popen[str] | None = None
    published = False
    try:
        request_path.write_text(json.dumps({
            "frames_path": str(frames),
            "output_path": str(temp_root / "artifacts"),
            "prompt_path": str(prompt),
            "model": model,
            "feather_radius": float(feather_radius),
            "defringe": defringe,
        }), encoding="utf-8")
        report(0.01, "Starting isolated SAM 2 process")
        process = subprocess.Popen(
            [str(_resolve_python()), "-u", str(_resolve_runner()), str(request_path)],
            cwd=str(Path(__file__).resolve().parents[2]),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        assert process.stderr is not None
        stderr_lines: deque[str] = deque(maxlen=200)

        def drain_stderr() -> None:
            for stderr_line in process.stderr:
                stderr_lines.append(stderr_line.rstrip())

        stderr_thread = Thread(target=drain_stderr, daemon=True)
        stderr_thread.start()
        result: dict[str, Any] | None = None
        for line in process.stdout:
            if cancelled():
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                raise Sam2ProcessError("SAM 2 job cancelled")
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise Sam2ProcessError("SAM 2 process emitted invalid JSON") from exc
            if event.get("type") == "progress":
                report(float(event["progress"]), str(event.get("message") or "Processing"))
            elif event.get("type") == "result" and isinstance(event.get("payload"), dict):
                result = event["payload"]
        return_code = process.wait()
        stderr_thread.join(timeout=2)
        process.stdout.close()
        process.stderr.close()
        if return_code != 0 or result is None:
            stderr = "\n".join(stderr_lines).strip()
            raise Sam2ProcessError(stderr[-4000:] or f"SAM 2 process exited with code {return_code}")

        artifacts = temp_root / "artifacts"
        if not artifacts.is_dir():
            raise Sam2ProcessError("SAM 2 process did not create artifacts")
        if output.exists():
            output.rmdir()
        artifacts.replace(output)
        published = True
        resolved_output = output.resolve()
        result["output_path"] = str(resolved_output)
        result["masks_path"] = str(resolved_output / "masks")
        result["rgba_path"] = str(resolved_output / "rgba")
        if "normalized_rgba_path" in result:
            result["normalized_rgba_path"] = str(resolved_output / "shared_canvas")
        if "shared_canvas_report_path" in result:
            result["shared_canvas_report_path"] = str(
                resolved_output / "shared_canvas" / "shared-canvas-report.json"
            )
        result["report_path"] = str(resolved_output / "sam2-rgba-report.json")
        report(1.0, "SAM 2 RGBA sequence completed")
        return result
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        shutil.rmtree(temp_root, ignore_errors=True)
        if not published and output.exists() and not any(output.iterdir()):
            output.rmdir()
