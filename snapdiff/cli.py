"""Command line interface: diff two snapshots into a JSON report."""

import argparse
import json
import os
import tempfile

from .report import build_report


def _atomic_write_json(path, payload):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".report-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
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


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="snapdiff",
        description="Compare two content-addressed snapshots and emit a JSON report.",
    )
    parser.add_argument("--old", required=True, help="old snapshot directory")
    parser.add_argument("--new", required=True, help="new snapshot directory")
    parser.add_argument("--out", required=True, help="path for the JSON report")
    args = parser.parse_args(argv)

    report = build_report(args.old, args.new)
    _atomic_write_json(args.out, report)

    summary = report["summary"]
    print(
        "targets={total} changed={changed} "
        "(added={added} deleted={deleted} modified={modified} "
        "unchanged={unchanged})".format(**summary)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

