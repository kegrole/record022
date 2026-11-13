import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from snapdiff import cli
from snapdiff.manifest import Manifest
from snapdiff.report import build_report
from snapdiff.store import ObjectStore

# Fixture targets deliberately use different names than the demo fixtures,
# so the tests prove classification does not depend on specific names.
V1_FIXTURE = {
    "page_body": ("text", "header\nmiddle\nfooter\n"),
    "settings": ("json", {"host": "a.example", "port": 1000, "tls": True}),
    "legacy_only": ("text", "only in the old snapshot\n"),
    "stable": ("text", "same content in both rounds\n"),
}

V2_FIXTURE = {
    "page_body": ("text", "header\nmiddle part A\nmiddle part B\nfooter\n"),
    "settings": ("json", {"host": "a.example", "port": 2000, "tls": True}),
    "fresh_only": ("text", "only in the new snapshot\n"),
    "stable": ("text", "same content in both rounds\n"),
}


def _encode(kind, content):
    if kind == "json":
        return (json.dumps(content, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return content.encode("utf-8")


def build_snapshot_pair(root):
    """Build v1/v2 snapshots sharing one object store; return (v1, v2)."""
    store = ObjectStore(os.path.join(root, "objects"))
    paths = {}
    for version, fixture in (("v1", V1_FIXTURE), ("v2", V2_FIXTURE)):
        manifest = Manifest()
        for name, (kind, content) in sorted(fixture.items()):
            digest = store.put(_encode(kind, content))
            manifest.add(name, digest, kind)
        path = os.path.join(root, version)
        manifest.save(os.path.join(path, "manifest.json"))
        paths[version] = path
    return paths["v1"], paths["v2"]


class SnapdiffTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="snapdiff-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.v1, self.v2 = build_snapshot_pair(self.tmp)
        self.report = build_report(self.v1, self.v2)
        self.records = {r["target"]: r for r in self.report["records"]}

    # Rule 1+2: exactly 5 records with the expected status breakdown.
    def test_record_count_and_statuses(self):
        self.assertEqual(len(self.report["records"]), 5)
        by_status = {}
        for record in self.report["records"]:
            by_status.setdefault(record["status"], []).append(record["target"])
        self.assertEqual(by_status.get("added"), ["fresh_only"])
        self.assertEqual(by_status.get("deleted"), ["legacy_only"])
        self.assertEqual(sorted(by_status.get("modified", [])),
                         ["page_body", "settings"])
        self.assertEqual(by_status.get("unchanged"), ["stable"])
        summary = self.report["summary"]
        self.assertEqual(summary["total"], 5)
        self.assertEqual(summary["added"], 1)
        self.assertEqual(summary["deleted"], 1)
        self.assertEqual(summary["modified"], 2)
        self.assertEqual(summary["unchanged"], 1)
        self.assertEqual(summary["changed"], 4)

    # Rule 3: the text diff names the exact removed and added lines.
    def test_text_line_diff(self):
        diff = self.records["page_body"]["diff"]
        self.assertEqual(diff["type"], "text")
        self.assertEqual(diff["removed_lines"],
                         [{"line": 2, "text": "middle"}])
        self.assertEqual(diff["added_lines"],
                         [{"line": 2, "text": "middle part A"},
                          {"line": 3, "text": "middle part B"}])

    # Rule 4: the JSON diff gives field name, old value and new value.
    def test_json_field_diff(self):
        diff = self.records["settings"]["diff"]
        self.assertEqual(diff["type"], "json")
        self.assertEqual(diff["changed"], {"port": {"old": 1000, "new": 2000}})
        self.assertEqual(diff["added_fields"], {})
        self.assertEqual(diff["removed_fields"], {})

    # Rule 5: content addressing dedupes identical content.
    def test_content_addressed_dedup(self):
        objects_dir = os.path.join(self.tmp, "objects")
        store = ObjectStore(objects_dir)
        data = b"same content in both rounds\n"
        digest = hashlib.sha256(data).hexdigest()
        # The unchanged target appears in both versions but is stored once.
        self.assertTrue(os.path.exists(os.path.join(objects_dir, digest)))
        self.assertEqual(store.digests().count(digest), 1)
        # v1 has 4 targets, v2 adds 1 new + 2 modified = 7 distinct blocks.
        self.assertEqual(len(store.digests()), 7)
        # Storing the same bytes again is a no-op returning the same digest.
        again = store.put(data)
        self.assertEqual(again, digest)
        self.assertEqual(len(store.digests()), 7)

    # Rule 6a: an interrupted object write leaves no partial/visible file.
    def test_atomic_object_write_interrupted(self):
        objects_dir = os.path.join(self.tmp, "atomic-objects")
        store = ObjectStore(objects_dir)
        with mock.patch("snapdiff.store.os.replace",
                        side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                store.put(b"partial content")
        self.assertEqual(os.listdir(objects_dir), [])

    # Rule 6b: an interrupted manifest write keeps the old manifest intact.
    def test_atomic_manifest_write_interrupted(self):
        path = os.path.join(self.tmp, "atomic", "manifest.json")
        manifest = Manifest()
        manifest.add("one", "a" * 64, "text")
        manifest.save(path)
        before = Manifest.load(path).targets

        manifest.add("two", "b" * 64, "text")
        with mock.patch("snapdiff.manifest.os.replace",
                        side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                manifest.save(path)

        self.assertEqual(Manifest.load(path).targets, before)
        self.assertEqual(os.listdir(os.path.dirname(path)), ["manifest.json"])

    # Rule 7: every record has all fields; diff is non-empty unless unchanged.
    def test_record_fields_complete(self):
        for record in self.report["records"]:
            self.assertIn("target", record)
            self.assertIn("status", record)
            self.assertIn("diff", record)
            self.assertIn(record["status"],
                          ("added", "deleted", "modified", "unchanged"))
            if record["status"] == "unchanged":
                self.assertEqual(record["diff"], {})
            else:
                self.assertTrue(record["diff"],
                                "diff must not be empty for " + record["target"])

    # CLI end-to-end: writes the report and prints a one-line summary.
    def test_cli_end_to_end(self):
        out_path = os.path.join(self.tmp, "out", "diff.json")
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = cli.main(["--old", self.v1, "--new", self.v2,
                           "--out", out_path])
        self.assertEqual(rc, 0)
        line = stdout.getvalue().strip()
        self.assertIn("targets=5", line)
        self.assertIn("changed=4", line)
        self.assertIn("added=1", line)
        self.assertIn("deleted=1", line)
        self.assertIn("modified=2", line)
        self.assertIn("unchanged=1", line)
        with open(out_path, "r", encoding="utf-8") as fh:
            report = json.load(fh)
        self.assertEqual(report["summary"]["total"], 5)
        self.assertEqual(len(report["records"]), 5)


if __name__ == "__main__":
    unittest.main()

