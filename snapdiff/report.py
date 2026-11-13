"""Build a diff report between two snapshot directories."""

import json
import os

from .diffjson import diff_json, flatten
from .difftext import diff_text
from .manifest import Manifest
from .store import ObjectStore


class Snapshot:
    def __init__(self, root, manifest, store):
        self.root = root
        self.manifest = manifest
        self.store = store

    def read_text(self, digest):
        return self.store.get(digest).decode("utf-8")

    def read_json(self, digest):
        return json.loads(self.store.get(digest).decode("utf-8"))


def load_snapshot(path):
    """Load a snapshot directory.

    Objects live in <path>/objects, or in a shared store at
    <parent>/objects when several snapshot versions sit side by side.
    """
    manifest = Manifest.load(os.path.join(path, "manifest.json"))
    objects = os.path.join(path, "objects")
    if not os.path.isdir(objects):
        shared = os.path.join(os.path.dirname(os.path.abspath(path)), "objects")
        if os.path.isdir(shared):
            objects = shared
    return Snapshot(path, manifest, ObjectStore(objects))


def _added_record(snapshot, name, entry):
    if entry["type"] == "json":
        diff = {
            "type": "json",
            "changed": {},
            "added_fields": flatten(snapshot.read_json(entry["sha256"])),
            "removed_fields": {},
        }
    else:
        lines = snapshot.read_text(entry["sha256"]).splitlines()
        diff = {
            "type": "text",
            "added_lines": [
                {"line": n + 1, "text": line} for n, line in enumerate(lines)
            ],
            "removed_lines": [],
        }
    return {"target": name, "status": "added", "diff": diff}


def _deleted_record(snapshot, name, entry):
    if entry["type"] == "json":
        diff = {
            "type": "json",
            "changed": {},
            "added_fields": {},
            "removed_fields": flatten(snapshot.read_json(entry["sha256"])),
        }
    else:
        lines = snapshot.read_text(entry["sha256"]).splitlines()
        diff = {
            "type": "text",
            "added_lines": [],
            "removed_lines": [
                {"line": n + 1, "text": line} for n, line in enumerate(lines)
            ],
        }
    return {"target": name, "status": "deleted", "diff": diff}


def _modified_record(old, new, name, old_entry, new_entry):
    kind = new_entry.get("type", old_entry.get("type", "text"))
    if kind == "json":
        diff = diff_json(
            old.read_json(old_entry["sha256"]),
            new.read_json(new_entry["sha256"]),
        )
    else:
        diff = diff_text(
            old.read_text(old_entry["sha256"]),
            new.read_text(new_entry["sha256"]),
        )
    return {"target": name, "status": "modified", "diff": diff}


def build_report(old_dir, new_dir):
    """Compare two snapshots and return the report as a dict."""
    old = load_snapshot(old_dir)
    new = load_snapshot(new_dir)
    old_targets = old.manifest.targets
    new_targets = new.manifest.targets

    records = []
    counts = {"added": 0, "deleted": 0, "modified": 0, "unchanged": 0}
    for name in sorted(set(old_targets) | set(new_targets)):
        if name not in old_targets:
            record = _added_record(new, name, new_targets[name])
            status = "added"
        elif name not in new_targets:
            record = _deleted_record(old, name, old_targets[name])
            status = "deleted"
        elif old_targets[name]["sha256"] == new_targets[name]["sha256"]:
            record = {"target": name, "status": "unchanged", "diff": {}}
            status = "unchanged"
        else:
            record = _modified_record(
                old, new, name, old_targets[name], new_targets[name]
            )
            status = "modified"
        counts[status] += 1
        records.append(record)

    summary = {
        "total": len(records),
        "added": counts["added"],
        "deleted": counts["deleted"],
        "modified": counts["modified"],
        "unchanged": counts["unchanged"],
        "changed": counts["added"] + counts["deleted"] + counts["modified"],
    }
    return {"records": records, "summary": summary}

