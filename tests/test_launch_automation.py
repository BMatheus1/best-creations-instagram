"""Testes offline da importação, ordem e publicação (NUNCA chamam a Meta)."""
from __future__ import annotations
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import import_launch_assets as importer
import publish_launch as publisher
import run_launch_batch as batch


def make_items(temp: Path):
    root = temp / "media" / "launch"
    root.mkdir(parents=True)
    items = []
    for i in range(1, 28):
        channel = "story" if i <= 7 else "feed"
        path = f"media/launch/{i:02d}_{channel}.jpg"
        blob = b"\xff\xd8\xff" + f"fake-original-image-{i}".encode()
        (temp / path).write_bytes(blob)
        items.append({
            "id": f"bc-launch-{i:03d}", "sequence": i, "channel": channel,
            "media_type": "STORY" if channel == "story" else "IMAGE",
            "title": f"Post {i}", "classification": "concept",
            "image_path": path, "image_url": f"https://raw.githubusercontent.com/BMatheus1/best-creations-instagram/main/{path}",
            "sha256": hashlib.sha256(blob).hexdigest(),
            "caption": "" if channel == "story" else f"Foto numero {i}",
            "status": "approved", "approved_by": "owner",
        })
    (temp / "content").mkdir()
    (temp / "content" / "launch_queue.json").write_text(json.dumps(items))
    (temp / "state").mkdir()
    (temp / "state" / "launch_publications.json").write_text("{}")
    return items


def create_test_zip(path: Path, alter=None):
    """Artefato gerado na memória, sem dados reais nem rede."""
    from PIL import Image
    def jpg(size):
        stream = io.BytesIO()
        Image.new("RGB", size, (12, 13, 14)).save(stream, format="JPEG")
        return stream.getvalue()
    story = jpg((576, 1024))
    feed = jpg((400, 500))
    items = []
    files = {}
    for i in range(1, 28):
        ch = "story" if i <= 7 else "feed"
        n = i if ch == "story" else i - 7
        name = f"{'01_STORIES_PUBLICAR_PRIMEIRO' if ch == 'story' else '02_FEED_PUBLICAR_DEPOIS'}/{n:02d}_test.jpg"
        items.append({
            "order": n, "channel": ch, "name": f"Test {i}", "file": name,
            "caption": "Conteúdo fictício" if ch == "feed" else "",
        })
        files[name] = story if ch == "story" else feed
    if alter:
        alter(items, files)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifesto_publicacao.json", json.dumps({
            "account": "bestcreations011", "items": items,
        }))
        for k, v in files.items():
            z.writestr(k, v)


class ImporterTests(unittest.TestCase):
    def test_validates_paths(self):
        self.assertFalse(importer._valid_name("../bad.jpg"))
        self.assertFalse(importer._valid_name("/etc/passwd"))
        self.assertFalse(importer._valid_name("hello\\test.jpg"))
        self.assertTrue(importer._valid_name("media/launch/01_story.jpg"))

    def test_imports_exactly_27_in_correct_order(self):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            zip_path = temp / "images.zip"
            create_test_zip(zip_path)
            with patch.object(importer, "ROOT", temp), \
                 patch.object(importer, "QUEUE", temp / "content" / "launch_queue.json"), \
                 patch.object(importer, "MEDIA", temp / "media" / "launch"):
                self.assertEqual(importer.install(zip_path), 27)
                items = json.loads((temp / "content" / "launch_queue.json").read_text())
            self.assertEqual([i["media_type"] for i in items[:7]], ["STORY"] * 7)
            self.assertEqual([i["media_type"] for i in items[7:]], ["IMAGE"] * 20)
            self.assertEqual(items[7]["sequence"], 8)
            self.assertTrue((temp / "media/launch/27_feed.jpg").exists())

    def test_rejects_wrong_order(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "wrong.zip"
            create_test_zip(p, lambda items, files: items.__setitem__(0, dict(items[0], order=2)))
            with self.assertRaises(ValueError):
                importer.assemble(p)

    def test_rejects_missing_image(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "missing.zip"
            def alter(items, files):
                files.pop(items[3]["file"])
            create_test_zip(p, alter)
            with self.assertRaises(KeyError):
                importer.assemble(p)

    def test_does_not_overwrite_different_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            p = temp / "images.zip"
            create_test_zip(p)
            (temp / "content").mkdir()
            (temp / "content" / "launch_queue.json").write_text('[{"id":"previous"}]')
            with patch.object(importer, "ROOT", temp), \
                 patch.object(importer, "QUEUE", temp / "content" / "launch_queue.json"), \
                 patch.object(importer, "MEDIA", temp / "media" / "launch"):
                with self.assertRaises(RuntimeError):
                    importer.install(p)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.temp = Path(self.tmp.name)
        self.items = make_items(self.temp)
        patches = [
            patch.object(publisher, "ROOT", self.temp),
            patch.object(publisher, "QUEUE_PATH", self.temp / "content" / "launch_queue.json"),
            patch.object(publisher, "LEDGER_PATH", self.temp / "state" / "launch_publications.json"),
        ]
        self.patches = patches
        for p in patches:
            p.start()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def test_reads_complete_ordered_media(self):
        self.assertEqual(len(publisher.read_queue()), 27)
        self.assertEqual(publisher.next_item(self.items, {}), self.items[0])

    def test_missing_media_is_blocked(self):
        (self.temp / "media/launch/12_feed.jpg").unlink()
        with self.assertRaises(publisher.Blocked):
            publisher.read_queue()

    def test_tampered_sha_is_blocked(self):
        (self.temp / "media/launch/01_story.jpg").write_bytes(b"\xff\xd8\xffaltered")
        with self.assertRaises(publisher.Blocked):
            publisher.read_queue()

    def test_must_publish_stories_before_feed(self):
        ledger = {x["id"]: {"status": "published"} for x in self.items[:7]}
        self.assertEqual(publisher.next_item(self.items, ledger)["id"], "bc-launch-008")

    def test_pending_attempt_stops_everything(self):
        ledger = {self.items[0]["id"]: {"status": "publish_requested"}}
        with self.assertRaises(publisher.Blocked):
            publisher.next_item(self.items, ledger)

    def test_feed_two_to_nine_are_excluded_and_next_is_ten(self):
        exclusions = {"excluded_ids": [f"bc-launch-{i:03d}" for i in range(9, 17)]}
        (self.temp / "content" / "launch_exclusions.json").write_text(json.dumps(exclusions))
        ledger = {item["id"]: {"status": "published"} for item in self.items[:9]}
        self.assertEqual(publisher.next_item(self.items, ledger)["id"], "bc-launch-017")
        self.assertEqual(publisher.read_exclusions(), set(exclusions["excluded_ids"]))

    def test_canceled_item_with_unconfirmed_attempt_blocks(self):
        exclusions = {"excluded_ids": ["bc-launch-010"]}
        (self.temp / "content" / "launch_exclusions.json").write_text(json.dumps(exclusions))
        ledger = {item["id"]: {"status": "published"} for item in self.items[:9]}
        ledger["bc-launch-010"] = {"status": "container_created"}
        with self.assertRaises(publisher.Blocked):
            publisher.next_item(self.items, ledger)

    def test_manual_cannot_publish_without_explicit_confirmation(self):
        with patch.dict(os.environ, {"INSTAGRAM_LAUNCH_ENABLE_MANUAL": "true"}):
            with self.assertRaises(publisher.Blocked):
                publisher.execute("manual", "incorrect")

    def test_auto_cannot_run_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(publisher.Blocked):
                publisher.execute("auto")

    def test_dry_run_does_not_call_meta_or_commit(self):
        with patch.object(publisher, "graph_request", side_effect=AssertionError("Network forbidden")), \
             patch.object(publisher, "commit_ledger", side_effect=AssertionError("Commit forbidden")):
            publisher.execute("dry-run")

    def test_dry_run_during_wait_is_not_error_or_publication(self):
        first = self.items[0]
        just_published = publisher.utcnow() - timedelta(minutes=1)
        ledger = {
            first["id"]: {
                "status": "published",
                "published_at": just_published.isoformat(),
                "channel": "story",
            }
        }
        (self.temp / "state" / "launch_publications.json").write_text(json.dumps(ledger))
        with patch.object(publisher, "graph_request", side_effect=AssertionError("Network forbidden")), \
             patch.object(publisher, "commit_ledger", side_effect=AssertionError("Commit forbidden")):
            publisher.execute("dry-run")
            with patch.dict(os.environ, {"INSTAGRAM_LAUNCH_ENABLE_AUTO": "true"}):
                publisher.execute("auto")

    def test_five_minute_feed_interval(self):
        now = datetime(2026, 11, 2, 15, tzinfo=timezone.utc)
        published = now - timedelta(minutes=4, seconds=59)
        ledger = {"prior": {"status": "published", "published_at": published.isoformat(), "channel": "feed"}}
        with self.assertRaises(publisher.Blocked):
            publisher.check_pacing(self.items[9], ledger, now)
        publisher.check_pacing(self.items[9], ledger, now + timedelta(seconds=1))

    def test_five_minute_story_interval(self):
        now = datetime(2026, 11, 2, 15, tzinfo=timezone.utc)
        published = now - timedelta(minutes=4, seconds=59)
        ledger = {"prior": {"status": "published", "published_at": published.isoformat(), "channel": "story"}}
        with self.assertRaises(publisher.Blocked):
            publisher.check_pacing(self.items[1], ledger, now)
        publisher.check_pacing(self.items[1], ledger, now + timedelta(seconds=1))

    def test_five_minute_transition_from_last_story_to_first_feed(self):
        now = datetime(2026, 11, 2, 15, tzinfo=timezone.utc)
        published = now - timedelta(minutes=4, seconds=59)
        ledger = {"prior": {"status": "published", "published_at": published.isoformat(), "channel": "story"}}
        with self.assertRaises(publisher.Blocked):
            publisher.check_pacing(self.items[7], ledger, now)
        publisher.check_pacing(self.items[7], ledger, now + timedelta(seconds=1))

    def test_story_media_payload_has_no_caption(self):
        events = []
        def graph(token, method, path, fields):
            events.append((method, path, fields))
            if path.endswith("/media"):
                return {"id": "container"}
            if path == "container":
                return {"status_code": "FINISHED"}
            return {"id": "published"}
        with patch.object(publisher, "verify_account", return_value="account"), \
             patch.object(publisher, "verify_public_image"), \
             patch.object(publisher, "commit_ledger"), \
             patch.object(publisher, "graph_request", side_effect=graph):
            publisher.publish_item("fake-token", self.items[0])
            self.assertEqual(events[0][2]["media_type"], "STORIES")
            self.assertNotIn("caption", events[0][2])
            self.assertEqual(events[-1][1], "account/media_publish")

    def test_feed_media_payload_includes_caption(self):
        events = []
        def graph(token, method, path, fields):
            events.append((method, path, fields))
            if path.endswith("/media"):
                return {"id": "container"}
            if path == "container":
                return {"status_code": "FINISHED"}
            return {"id": "published"}
        with patch.object(publisher, "verify_account", return_value="account"), \
             patch.object(publisher, "verify_public_image"), \
             patch.object(publisher, "commit_ledger"), \
             patch.object(publisher, "graph_request", side_effect=graph):
            publisher.publish_item("fake-token", self.items[7])
            self.assertEqual(events[0][2]["caption"], self.items[7]["caption"])
            self.assertNotIn("media_type", events[0][2])

    def test_batch_requires_both_auto_authorizations(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(publisher.Blocked):
                batch.execute()
        with patch.dict(os.environ, {"INSTAGRAM_LAUNCH_ENABLE_AUTO": "true", "INSTAGRAM_ACCESS_TOKEN": "test"}, clear=True):
            with self.assertRaises(publisher.Blocked):
                batch.execute()

    def test_batch_stops_when_previous_attempt_is_ambiguous(self):
        ledger = {"bc-launch-001": {"status": "attempt_started"}}
        (self.temp / "state" / "launch_publications.json").write_text(json.dumps(ledger))
        env = {
            "INSTAGRAM_LAUNCH_ENABLE_AUTO": "true",
            "INSTAGRAM_LAUNCH_VARIABLE_ENABLED": "true",
            "INSTAGRAM_ACCESS_TOKEN": "test",
        }
        with patch.dict(os.environ, env, clear=True), \
             patch.object(publisher, "publish_item", side_effect=AssertionError("Must never republish")):
            with self.assertRaises(publisher.Blocked):
                batch.execute()

    def test_batch_keeps_order_and_skips_already_published_first_story(self):
        published_at = (publisher.utcnow() - timedelta(minutes=20)).isoformat()
        ledger = {"bc-launch-001": {"status": "published", "published_at": published_at, "channel": "story"}}
        (self.temp / "state" / "launch_publications.json").write_text(json.dumps(ledger))
        called = []

        def fake_publish(token, item):
            current = publisher.read_ledger()
            self.assertNotIn(item["id"], current)
            current[item["id"]] = {
                "status": "published", "channel": item["channel"],
                "published_at": publisher.utcnow().isoformat(),
            }
            (self.temp / "state" / "launch_publications.json").write_text(json.dumps(current))
            called.append(item["id"])

        env = {
            "INSTAGRAM_LAUNCH_ENABLE_AUTO": "true",
            "INSTAGRAM_LAUNCH_VARIABLE_ENABLED": "true",
            "INSTAGRAM_ACCESS_TOKEN": "test",
        }
        with patch.dict(os.environ, env, clear=True), \
             patch.object(publisher, "publish_item", side_effect=fake_publish), \
             patch.object(publisher, "check_pacing"), \
             patch.object(batch, "seconds_until_allowed", return_value=0), \
             patch.object(batch.time, "sleep", side_effect=AssertionError("Should not wait")):
            batch.execute()

        self.assertEqual(called, [f"bc-launch-{i:03d}" for i in range(2, 28)])
        self.assertEqual(len(publisher.read_ledger()), 27)

    def test_batch_waits_for_remaining_cooldown_without_publishing(self):
        published_at = (publisher.utcnow() - timedelta(seconds=30)).isoformat()
        ledger = {"bc-launch-001": {"status": "published", "published_at": published_at, "channel": "story"}}
        (self.temp / "state" / "launch_publications.json").write_text(json.dumps(ledger))
        env = {
            "INSTAGRAM_LAUNCH_ENABLE_AUTO": "true",
            "INSTAGRAM_LAUNCH_VARIABLE_ENABLED": "true",
            "INSTAGRAM_ACCESS_TOKEN": "test",
        }
        class StopTest(Exception):
            pass
        with patch.dict(os.environ, env, clear=True), \
             patch.object(publisher, "publish_item", side_effect=AssertionError("Cannot publish before interval")), \
             patch.object(batch.time, "sleep", side_effect=StopTest) as sleeper:
            with self.assertRaises(StopTest):
                batch.execute()
            self.assertGreater(sleeper.call_args.args[0], 0)
            self.assertLessEqual(sleeper.call_args.args[0], 30)

    def test_wrong_instagram_account_blocked(self):
        with patch.object(publisher, "graph_request", return_value={"id": "1", "username": "someone_else", "account_type": "BUSINESS"}):
            with self.assertRaises(publisher.Blocked):
                publisher.verify_account("fake", self.items[0])

    def test_creator_story_blocked_safely(self):
        with patch.object(publisher, "graph_request", return_value={"id": "1", "username": "bestcreations011", "account_type": "CREATOR"}):
            with self.assertRaises(publisher.Blocked):
                publisher.verify_account("fake", self.items[0])


if __name__ == "__main__":
    unittest.main()
