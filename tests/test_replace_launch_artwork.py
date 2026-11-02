"""Testes offline do importador de artes substitutas; nenhuma chamada para Meta/GitHub."""
from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import replace_launch_artwork as replacement


class ReplacementTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        (self.root / "media" / "launch").mkdir(parents=True)
        (self.root / "content").mkdir()
        (self.root / "state").mkdir()
        queue = []
        self.new_images = {}
        for seq in range(1, 28):
            channel = "story" if seq <= 7 else "feed"
            identifier = f"bc-launch-{seq:03d}"
            path = f"media/launch/{seq:02d}_{channel}.jpg"
            queue.append({
                "id": identifier, "sequence": seq, "channel": channel,
                "image_path": path, "sha256": hashlib.sha256(b"old").hexdigest(),
                "caption": f"Legenda original do item {seq}", "status": "approved",
            })
            if identifier in replacement.EXPECTED_IDS:
                self.new_images[identifier] = self.jpeg((seq * 7 % 256, 24, 56))
                (self.root / path).write_bytes(b"old")
        self.queue_path = self.root / "content" / "launch_queue.json"
        self.queue_path.write_text(json.dumps(queue))
        published = {
            identifier: {"status": "published"}
            for identifier in ("bc-launch-020", "bc-launch-022", "bc-launch-023", "bc-launch-024")
        }
        (self.root / "state" / "launch_publications.json").write_text(json.dumps(published))
        self.archive_path = self.root / "replacement.zip"
        self.create_zip()

    @staticmethod
    def jpeg(rgb):
        stream = io.BytesIO()
        Image.new("RGB", (1080, 1080), rgb).save(stream, "JPEG")
        return stream.getvalue()

    def create_zip(self, corrupt_id=None):
        manifest = {
            "type": "best_creations_feed_replacement", "account": "bestcreations011", "items": [],
        }
        with zipfile.ZipFile(self.archive_path, "w", zipfile.ZIP_DEFLATED) as z:
            for identifier in sorted(self.new_images):
                seq = int(identifier.rsplit("-", 1)[-1])
                path = f"media/launch/{seq:02d}_feed.jpg"
                digest = hashlib.sha256(self.new_images[identifier]).hexdigest()
                manifest["items"].append({
                    "id": identifier, "sequence": seq, "path": path,
                    "sha256": ("a" * 64 if identifier == corrupt_id else digest),
                })
                z.writestr(path, self.new_images[identifier])
            z.writestr("manifesto_substituicao.json", json.dumps(manifest))

    def test_dry_run_validates_but_changes_nothing(self):
        count = replacement.apply(self.archive_path, root=self.root)
        self.assertEqual(count, 3)
        queue = json.loads(self.queue_path.read_text())
        self.assertEqual(queue[24]["sha256"], hashlib.sha256(b"old").hexdigest())

    def test_apply_updates_only_pending_three(self):
        count = replacement.apply(self.archive_path, dry_run=False, root=self.root)
        self.assertEqual(count, 3)
        queue = json.loads(self.queue_path.read_text())
        for seq in (20, 22, 23, 24):
            self.assertEqual((self.root / f"media/launch/{seq:02d}_feed.jpg").read_bytes(), b"old")
            self.assertEqual(queue[seq-1]["sha256"], hashlib.sha256(b"old").hexdigest())
        for seq in (25, 26, 27):
            identifier = f"bc-launch-{seq:03d}"
            self.assertEqual((self.root / f"media/launch/{seq:02d}_feed.jpg").read_bytes(), self.new_images[identifier])
            self.assertEqual(queue[seq-1]["sha256"], hashlib.sha256(self.new_images[identifier]).hexdigest())
            self.assertEqual(queue[seq-1]["caption"], f"Legenda original do item {seq}")

    def test_blocks_ambiguous_attempt(self):
        ledger_path = self.root / "state" / "launch_publications.json"
        ledger = json.loads(ledger_path.read_text())
        ledger["bc-launch-025"] = {"status": "publish_requested"}
        ledger_path.write_text(json.dumps(ledger))
        with self.assertRaises(replacement.ImportErrorSafe):
            replacement.apply(self.archive_path, dry_run=False, root=self.root)
        self.assertEqual((self.root / "media/launch/25_feed.jpg").read_bytes(), b"old")

    def test_invalid_checksum_blocks_without_writing(self):
        self.create_zip(corrupt_id="bc-launch-026")
        with self.assertRaises(replacement.ImportErrorSafe):
            replacement.apply(self.archive_path, dry_run=False, root=self.root)
        self.assertEqual((self.root / "media/launch/25_feed.jpg").read_bytes(), b"old")

    def test_idempotent_second_run(self):
        replacement.apply(self.archive_path, dry_run=False, root=self.root)
        self.assertEqual(replacement.apply(self.archive_path, dry_run=False, root=self.root), 0)


if __name__ == "__main__":
    unittest.main()
