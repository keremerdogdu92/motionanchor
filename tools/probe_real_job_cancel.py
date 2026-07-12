from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from motionanchor_worker.jobs.media import MediaJobService

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "fixtures" / "cat-trap" / "videos" / "dash.mp4"


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "frames"
        service = MediaJobService()
        job_id = service.submit_extract_frames(str(SOURCE), str(output))
        time.sleep(0.05)
        service.cancel(job_id)
        deadline = time.time() + 10
        snapshot = service.status(job_id)
        while snapshot["status"] not in {"completed", "failed", "cancelled"}:
            if time.time() >= deadline:
                raise RuntimeError("cancellation probe timed out")
            time.sleep(0.02)
            snapshot = service.status(job_id)
        artifact_count = len(list(output.glob("*"))) if output.exists() else 0
        print(snapshot["status"], snapshot["cancellation_requested"], artifact_count)


if __name__ == "__main__":
    main()
