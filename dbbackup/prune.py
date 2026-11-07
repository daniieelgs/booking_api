"""Retention rules.

Pure functions plus a tiny stdlib-only CLI so the very same code can run on the
secondary server (``python3 -m dbbackup.prune --dir ... --keep-dumps 3``), where
retention is enforced by the receiver itself: a compromised primary can never
delete the copies it already shipped.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

DUMP_RE = re.compile(r'^dump-(\d{8}T\d{6})\.sql\.gz(\.age)?$')
META_RE = re.compile(r'^dump-(\d{8}T\d{6})\.meta\.json$')
BINLOG_RE = re.compile(r'^(.+)\.(\d{6})\.gz(\.age)?$')


def dumps_to_delete(dump_names: Iterable[str], keep: int, protected: Iterable[str] = ()) -> List[str]:
    """Names of dumps to delete: everything except the newest ``keep`` and the protected ones."""
    names = sorted(n for n in dump_names if DUMP_RE.match(n))  # stamp sorts chronologically
    protected = set(protected)
    survivors = set(names[-keep:]) if keep > 0 else set()
    return [n for n in names if n not in survivors and n not in protected]


def binlogs_older_than_seq(binlog_names: Iterable[str], min_seq: int) -> List[str]:
    """Binlogs whose sequence number is lower than ``min_seq`` (not needed by any kept dump)."""
    out = []
    for n in binlog_names:
        m = BINLOG_RE.match(n)
        if m and int(m.group(2)) < min_seq:
            out.append(n)
    return out


def _binlog_seq_from_filename(name: str) -> Optional[int]:
    m = re.match(r'^.+\.(\d{6})$', name)
    return int(m.group(1)) if m else None


def prune_remote_dir(directory: Path, keep_dumps: int, dry_run: bool = False, now: Optional[float] = None) -> List[str]:
    """Retention for the receiving directory on the secondary (flat layout).

    Keeps the newest ``keep_dumps`` dumps (with their .meta.json) and the binlogs
    needed to roll forward from the oldest kept dump. If the metadata of the
    oldest kept dump is unreadable, no binlog is deleted (fail safe).
    """
    directory = Path(directory)
    deleted: List[str] = []
    files = sorted(p.name for p in directory.iterdir() if p.is_file())

    # A dump only counts if both its data file and its meta are present.
    complete = [n for n in files if DUMP_RE.match(n) and f"dump-{DUMP_RE.match(n).group(1)}.meta.json" in files]
    doomed = dumps_to_delete(complete, keep_dumps)
    for n in doomed:
        stamp = DUMP_RE.match(n).group(1)
        deleted.extend([n, f'dump-{stamp}.meta.json'])

    kept = [n for n in complete if n not in doomed]
    if kept:
        oldest_meta = f'dump-{DUMP_RE.match(kept[0]).group(1)}.meta.json'
        try:
            meta = json.loads((directory / oldest_meta).read_text(encoding='utf-8'))
            min_seq = _binlog_seq_from_filename(meta['binlog_file'])
        except (OSError, ValueError, KeyError):
            min_seq = None
        if min_seq is not None:
            deleted.extend(binlogs_older_than_seq(files, min_seq))

    # Orphans of interrupted transfers (rsync temp files) older than a day.
    now = time.time() if now is None else now
    for n in files:
        if n.startswith('.') and now - (directory / n).stat().st_mtime > 86400:
            deleted.append(n)

    if not dry_run:
        for n in deleted:
            try:
                (directory / n).unlink()
            except FileNotFoundError:
                pass
    return deleted


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description='Apply backup retention in a receiving directory.')
    ap.add_argument('--dir', required=True)
    ap.add_argument('--keep-dumps', type=int, default=3)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args(argv)
    if args.keep_dumps < 1:
        print('--keep-dumps must be >= 1', file=sys.stderr)
        return 2
    if not os.path.isdir(args.dir):
        print(f'{args.dir} is not a directory', file=sys.stderr)
        return 2
    deleted = prune_remote_dir(Path(args.dir), args.keep_dumps, dry_run=args.dry_run)
    for n in deleted:
        print(('would delete ' if args.dry_run else 'deleted ') + n)
    return 0


if __name__ == '__main__':
    sys.exit(main())
