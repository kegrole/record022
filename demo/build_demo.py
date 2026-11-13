"""Regenerate the demo snapshots demo/v1 and demo/v2.

Both versions share a single object store at demo/objects/ so that content
appearing in both versions is stored exactly once (content addressing).

Fixture rules:
  - notes.txt    : text, modified (one line becomes two lines)
  - config.json  : json, modified (one field value changes)
  - removed.txt  : text, only in v1 (deleted)
  - added.txt    : text, only in v2 (added)
  - same.txt     : text, identical in both (unchanged)
"""

import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from snapdiff.manifest import Manifest
from snapdiff.store import ObjectStore

DEMO_ROOT = os.path.dirname(os.path.abspath(__file__))

V1 = {
    "notes.txt": ("text", "alpha\nbeta\ngamma\n"),
    "config.json": ("json", {"host": "example.com", "port": 8080, "debug": False}),
    "removed.txt": ("text", "this target only exists in v1\n"),
    "same.txt": ("text", "identical in both versions\n"),
}

V2 = {
    "notes.txt": ("text", "alpha\nbeta part one\nbeta part two\ngamma\n"),
    "config.json": ("json", {"host": "example.com", "port": 9090, "debug": False}),
    "added.txt": ("text", "this target only exists in v2\n"),
    "same.txt": ("text", "identical in both versions\n"),
}


def _encode(kind, content):
    if kind == "json":
        return (json.dumps(content, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return content.encode("utf-8")


def build():
    for name in ("objects", "v1", "v2"):
        shutil.rmtree(os.path.join(DEMO_ROOT, name), ignore_errors=True)

    store = ObjectStore(os.path.join(DEMO_ROOT, "objects"))
    for version, targets in (("v1", V1), ("v2", V2)):
        manifest = Manifest()
        for name, (kind, content) in sorted(targets.items()):
            digest = store.put(_encode(kind, content))
            manifest.add(name, digest, kind)
        manifest.save(os.path.join(DEMO_ROOT, version, "manifest.json"))


if __name__ == "__main__":
    build()
    print("demo snapshots written to", DEMO_ROOT)

