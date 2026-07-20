"""Run the real Cat Trap fixture acceptance gate."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from motionanchor_worker.acceptance import validate_cat_trap_fixture, write_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=Path("../fixtures/cat-trap"))
    parser.add_argument("--report", type=Path, default=Path("../artifacts/acceptance/cat-trap-e2e.json"))
    args = parser.parse_args()
    report = validate_cat_trap_fixture(args.fixture)
    write_report(report, args.report)
    for check in report.checks:
        print(f"[{'PASS' if check.passed else 'FAIL'}] {check.name}: {check.detail}")
    print(f"Acceptance: {'PASS' if report.passed else 'FAIL'}")
    print(f"Report: {args.report.resolve()}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

