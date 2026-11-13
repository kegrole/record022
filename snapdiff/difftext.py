"""Line-level diff for text targets."""

import difflib


def diff_text(old_text, new_text):
    """Return line-level differences between two text blobs.

    Lines are 1-indexed. "removed_lines" refers to line numbers in the old
    text, "added_lines" to line numbers in the new text.
    """
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines)
    removed = []
    added = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("delete", "replace"):
            for n in range(i1, i2):
                removed.append({"line": n + 1, "text": old_lines[n]})
        if tag in ("insert", "replace"):
            for n in range(j1, j2):
                added.append({"line": n + 1, "text": new_lines[n]})
    return {"type": "text", "removed_lines": removed, "added_lines": added}

