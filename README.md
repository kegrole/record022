# snapdiff

Compare two rounds of site crawling: store each round as a content-addressed
snapshot, then diff two snapshots into a JSON report classifying every
target as added / deleted / modified / unchanged.

Pure Python standard library, no third-party dependencies.

## Snapshot format

A snapshot directory contains a `manifest.json`:

```json
{
  "version": 1,
  "targets": {
    "notes.txt": {"sha256": "<hex>", "type": "text"},
    "config.json": {"sha256": "<hex>", "type": "json"}
  }
}
```

Each target points at a content block. Blocks live in an object store:

- `<snapshot>/objects/` for a self-contained snapshot, or
- `<parent>/objects/` as a shared store when several snapshot versions sit
  side by side (the demo uses this layout: `demo/objects/` shared by
  `demo/v1/` and `demo/v2/`).

## Content addressing

Every block is stored under the sha256 of its bytes
(`objects/<sha256>`). Identical content therefore maps to the same file
name and is stored exactly once per store: an unchanged target shared by
v1 and v2 occupies a single block in the shared store.

## Atomic writes

Both object blocks and manifests are written atomically:

1. write the full payload to a temp file in the same directory,
2. `fsync` it,
3. `os.replace()` it onto the final name (atomic rename).

An interrupted write can leave at most an orphaned temp file
(`objects/.tmp-*`, `.manifest-*.tmp`), never a partial file under its
final name; temp files are removed on failure. A manifest either fully
switches to the new version or keeps the old one, never half-written.

## Diff rules

For each target in the union of both manifests:

- only in new: `added`
- only in old: `deleted`
- same sha256 in both: `unchanged`
- different sha256: `modified`, with a type-specific diff:
  - text: line-level diff (difflib.SequenceMatcher) reporting
    `removed_lines` / `added_lines` with 1-based line numbers;
  - json: field-level diff over flattened dotted paths, reporting
    `changed` (field to old/new), `added_fields`, `removed_fields`.

For added/deleted targets the diff carries the full content (all lines or
all fields on the corresponding side), so `diff` is only empty for
`unchanged`.

## Report format

```json
{
  "records": [
    {"target": "...", "status": "added|deleted|modified|unchanged",
     "diff": {}}
  ],
  "summary": {"total": 5, "added": 1, "deleted": 1, "modified": 2,
              "unchanged": 1, "changed": 4}
}
```

## Usage

```sh
python -m snapdiff.cli --old demo/v1 --new demo/v2 --out out/diff.json
```

Prints a one-line summary of counts to stdout and writes the JSON report.

Regenerate the demo snapshots (deterministic, same rules):

```sh
python demo/build_demo.py
```

Run the tests:

```sh
cd tests && python -m unittest test_snapdiff -v
# or from the repo root:
python -m unittest discover -s tests -v
```
