"""Snapshot manifest: maps each target name to its current content block."""

import json
import os
import tempfile

FORMAT_VERSION = 1


class Manifest:
    """A manifest records, per target, the sha256 of its content and its
    kind ("text" or "json")."""

    def __init__(self, targets=None):
        self.targets = dict(targets or {})

    def add(self, name, digest, kind):
        self.targets[name] = {"sha256": digest, "type": kind}

    def to_dict(self):
        return {"version": FORMAT_VERSION, "targets": self.targets}

    @classmethod
    def from_dict(cls, data):
        return cls(targets=data.get("targets", {}))

    @classmethod
    def load(cls, path):
        with open(path, "r", encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))
    def save(self, path):
        """Atomically replace the manifest at path (temp file + rename)."""
        directory = os.path.dirname(os.path.abspath(path))
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=directory, prefix=".manifest-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.to_dict(), fh, indent=2, sort_keys=True)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

