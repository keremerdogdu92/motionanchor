# worker/tests/test_protocol.py
"""Unit tests for motionanchor_worker.protocol."""

from __future__ import annotations

import json
import unittest

from motionanchor_worker import MAX_MESSAGE_BYTES, PROTOCOL_VERSION
from motionanchor_worker.errors import WorkerError
from motionanchor_worker.protocol import (
    TYPE_ERROR,
    TYPE_WORKER_PING,
    TYPE_WORKER_READY,
    envelope_to_json,
    make_envelope,
    make_error_envelope,
    new_message_id,
    parse_line,
    validate_envelope,
)


class TestNewMessageId(unittest.TestCase):
    def test_unique(self) -> None:
        ids = {new_message_id() for _ in range(200)}
        self.assertEqual(len(ids), 200)

    def test_is_uuid_format(self) -> None:
        mid = new_message_id()
        parts = mid.split("-")
        self.assertEqual(len(parts), 5)


class TestMakeEnvelope(unittest.TestCase):
    def test_minimal(self) -> None:
        env = make_envelope(message_type="test.hello")
        self.assertEqual(env["protocol_version"], PROTOCOL_VERSION)
        self.assertEqual(env["type"], "test.hello")
        self.assertIsNone(env["job_id"])
        self.assertIsInstance(env["message_id"], str)
        self.assertEqual(env["payload"], {})

    def test_explicit_ids(self) -> None:
        env = make_envelope(
            message_type="test.x",
            message_id="mid-1",
            job_id="jid-1",
            payload={"k": 1},
        )
        self.assertEqual(env["message_id"], "mid-1")
        self.assertEqual(env["job_id"], "jid-1")
        self.assertEqual(env["payload"], {"k": 1})


class TestMakeErrorEnvelope(unittest.TestCase):
    def test_contains_error_fields(self) -> None:
        from motionanchor_worker.errors import unknown_type

        err = unknown_type("foo.bar")
        env = make_error_envelope(err, in_reply_to="orig-1", job_id="j-1")
        self.assertEqual(env["type"], TYPE_ERROR)
        self.assertEqual(env["message_id"], "orig-1")
        self.assertEqual(env["job_id"], "j-1")
        self.assertEqual(env["payload"]["code"], "unknown_type")
        self.assertIn("foo.bar", env["payload"]["message"])


class TestEnvelopeToJson(unittest.TestCase):
    def test_single_line(self) -> None:
        env = make_envelope(message_type="t")
        raw = envelope_to_json(env)
        self.assertTrue(raw.endswith(b"\n"))
        parsed = json.loads(raw)
        self.assertEqual(parsed["type"], "t")

    def test_utf8(self) -> None:
        env = make_envelope(message_type="t", payload={"text": "\u00e9\u00e8"})
        raw = envelope_to_json(env)
        parsed = json.loads(raw)
        self.assertEqual(parsed["payload"]["text"], "\u00e9\u00e8")


class TestParseLine(unittest.TestCase):
    def test_blank_line(self) -> None:
        obj, err = parse_line(b"\n")
        self.assertIsNone(obj)
        self.assertIsNone(err)

    def test_valid_json(self) -> None:
        env = make_envelope(message_type="t")
        raw = envelope_to_json(env)
        obj, err = parse_line(raw)
        self.assertIsNone(err)
        self.assertIsNotNone(obj)
        assert obj is not None
        self.assertEqual(obj["type"], "t")

    def test_invalid_json(self) -> None:
        obj, err = parse_line(b"{bad json}\n")
        self.assertIsNone(obj)
        self.assertIsNotNone(err)
        assert err is not None
        self.assertEqual(err.code, "malformed_json")

    def test_non_object_json(self) -> None:
        obj, err = parse_line(b"42\n")
        self.assertIsNone(obj)
        self.assertIsNotNone(err)
        assert err is not None
        self.assertEqual(err.code, "malformed_json")
        self.assertIn("object", err.message)

    def test_over_size_limit(self) -> None:
        huge = b'{"x":"' + b"a" * (MAX_MESSAGE_BYTES + 100) + b'"}\n'
        obj, err = parse_line(huge)
        self.assertIsNone(obj)
        self.assertIsNotNone(err)
        assert err is not None
        self.assertEqual(err.code, "malformed_json")


class TestValidateEnvelope(unittest.TestCase):
    def _good(self) -> dict:
        return make_envelope(message_type="t")

    def test_valid(self) -> None:
        self.assertIsNone(validate_envelope(self._good()))

    def test_missing_type(self) -> None:
        obj = self._good()
        del obj["type"]
        err = validate_envelope(obj)
        self.assertIsNotNone(err)
        assert err is not None
        self.assertIn("type", err.message)

    def test_missing_message_id(self) -> None:
        obj = self._good()
        del obj["message_id"]
        err = validate_envelope(obj)
        self.assertIsNotNone(err)

    def test_missing_protocol_version(self) -> None:
        obj = self._good()
        del obj["protocol_version"]
        err = validate_envelope(obj)
        self.assertIsNotNone(err)

    def test_payload_not_dict(self) -> None:
        obj = self._good()
        obj["payload"] = "nope"
        err = validate_envelope(obj)
        self.assertIsNotNone(err)
        assert err is not None
        self.assertEqual(err.code, "malformed_json")


if __name__ == "__main__":
    unittest.main()
