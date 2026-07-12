# worker/tests/test_errors.py
"""Unit tests for motionanchor_worker.errors."""

from __future__ import annotations

import unittest

from motionanchor_worker.errors import (
    INTERNAL,
    MALFORMED_JSON,
    UNKNOWN_TYPE,
    WorkerError,
    internal,
    malformed_json,
    unknown_type,
)


class TestWorkerError(unittest.TestCase):
    """Frozen dataclass behaviour."""

    def test_is_immutable(self) -> None:
        err = WorkerError(code="x", message="y")
        with self.assertRaises(AttributeError):
            err.code = "z"  # type: ignore[misc]

    def test_details_defaults_none(self) -> None:
        err = WorkerError(code="a", message="b")
        self.assertIsNone(err.details)


class TestMalformedJson(unittest.TestCase):
    def test_code_and_message(self) -> None:
        err = malformed_json()
        self.assertEqual(err.code, MALFORMED_JSON)
        self.assertIn("JSON", err.message)

    def test_with_detail(self) -> None:
        err = malformed_json(detail="{bad")
        self.assertIsNotNone(err.details)
        assert err.details is not None
        self.assertEqual(err.details["raw_preview"], "{bad")


class TestUnknownType(unittest.TestCase):
    def test_includes_type(self) -> None:
        err = unknown_type("bogus.foo")
        self.assertEqual(err.code, UNKNOWN_TYPE)
        self.assertIn("bogus.foo", err.message)


class TestInternal(unittest.TestCase):
    def test_code(self) -> None:
        err = internal("kaboom")
        self.assertEqual(err.code, INTERNAL)
        self.assertEqual(err.message, "kaboom")


if __name__ == "__main__":
    unittest.main()
