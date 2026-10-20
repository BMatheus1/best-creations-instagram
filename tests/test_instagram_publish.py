import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import instagram_publish as p


def post(**changes):
    data = {
        "id": "bc-test-01", "type": "IMAGE", "status": "approved",
        "approved_by": "owner", "scheduled_at": "2020-01-01T10:00:00-03:00",
        "caption": "Teste", "media_urls": ["https://example.com/image.jpg"],
    }
    data.update(changes)
    return data


class PublishSecurityTests(unittest.TestCase):
    def test_draft_blocked(self):
        with self.assertRaisesRegex(RuntimeError, "não aprovado"):
            p.validate_for_publication(post(status="draft"), datetime.now(timezone.utc))

    def test_future_blocked(self):
        with self.assertRaisesRegex(RuntimeError, "não chegou"):
            p.validate_for_publication(post(scheduled_at="2099-01-01T10:00:00-03:00"), datetime.now(timezone.utc))

    def test_png_blocked(self):
        with self.assertRaisesRegex(RuntimeError, "JPEG"):
            p.validate_for_publication(post(media_urls=["https://example.com/image.png"]), datetime.now(timezone.utc))

    def test_jpeg_ok(self):
        p.validate_for_publication(post(), datetime.now(timezone.utc))

    def test_no_explicit_confirmation(self):
        with self.assertRaisesRegex(RuntimeError, "Confirmação inválida"):
            p.publish_one("bc-test-01", "fake-token", "manual", "")

    def test_wrong_account_blocked(self):
        with patch.object(p, "graph_request", return_value={"id": "123", "username": "outra_conta"}):
            with self.assertRaisesRegex(RuntimeError, "diferente"):
                p.ensure_verified_account("fake-token")

    def test_no_duplicate_after_attempt(self):
        with patch.object(p, "read_queue", return_value=[post()]), patch.object(p, "read_ledger", return_value={"bc-test-01": {"status": "attempt_started"}}):
            with self.assertRaisesRegex(RuntimeError, "evitar duplicação"):
                p.publish_one("bc-test-01", "fake-token", "manual", "PUBLICAR:bc-test-01")

    def test_scheduled_disabled(self):
        with patch.dict("os.environ", {"AUTO_PUBLISH_ENABLED": "false"}):
            self.assertIsNone(p.publish_one("bc-test-01", "fake-token", "schedule", ""))


if __name__ == "__main__":
    unittest.main()
