"""Content-addressed object storage with atomic writes."""

import hashlib
import os
import tempfile


class ObjectStore:
    """Stores content blocks named by their sha256 digest.

    Identical content always maps to the same file name, so each distinct
    block of content is stored exactly once per store.
    """

    def __init__(self, root):
        self.root = root

    def path_for(self, digest):
        return os.path.join(self.root, digest)

    def put(self, data):
        """Store bytes and return their sha256 digest.

        The write is atomic: content goes to a temp file in the same
        directory, is fsynced, then renamed into place. An interrupted
        write never leaves a partial object under its final name, and the
        temp file is cleaned up on failure.
        """
        digest = hashlib.sha256(data).hexdigest()
        path = self.path_for(digest)
        if os.path.exists(path):
            return digest
        os.makedirs(self.root, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return digest

    def get(self, digest):
        with open(self.path_for(digest), "rb") as fh:
            return fh.read()

    def has(self, digest):
        return os.path.exists(self.path_for(digest))

    def digests(self):
        if not os.path.isdir(self.root):
            return []
        return sorted(
            name for name in os.listdir(self.root)
            if not name.startswith(".tmp-")
        )

