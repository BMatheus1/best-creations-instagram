import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("social_manager", ROOT / "scripts" / "social_manager.py")
manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manager)


def item(**overrides):
    data = {
        "id": "test-post", "type": "IMAGE", "status": "draft",
        "caption": "Teste", "media_urls": ["https://example.com/image.png"],
        "scheduled_at": None, "approved_by": None,
    }
    data.update(overrides)
    return data


class SocialManagerTests(unittest.TestCase):
    def test_example_queue_is_valid(self):
        data = manager.read_queue(ROOT / "content" / "queue.json")
        self.assertGreater(len(data), 0)

    def test_drafts_are_never_eligible(self):
        self.assertEqual(manager.simulate([item()]), [])

    def test_approved_future_post_is_not_due(self):
        approved = item(status="approved", approved_by="owner", scheduled_at="2099-01-01T10:00:00-03:00")
        self.assertEqual(manager.simulate([approved], now=datetime(2026, 10, 20, tzinfo=timezone.utc)), [])

    def test_approved_due_post_is_eligible_only_in_simulation(self):
        approved = item(status="approved", approved_by="owner", scheduled_at="2020-01-01T10:00:00-03:00")
        self.assertEqual(len(manager.simulate([approved])), 1)

    def test_approval_requires_owner(self):
        with self.assertRaises(ValueError):
            manager.validate_item(item(status="approved", scheduled_at="2026-12-01T10:00:00-03:00"))

    def test_approval_requires_timezone(self):
        with self.assertRaises(ValueError):
            manager.validate_item(item(status="approved", approved_by="owner", scheduled_at="2026-12-01T10:00:00"))

    def test_http_media_rejected(self):
        with self.assertRaises(ValueError):
            manager.validate_item(item(media_urls=["http://example.com/a.png"]))

    def test_invalid_type_rejected(self):
        with self.assertRaises(ValueError):
            manager.validate_item(item(type="UNKNOWN"))


if __name__ == "__main__":
    unittest.main()
