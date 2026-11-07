"""Decide what ``scripts/promote-secondary.sh`` must restore.

Stdlib only and Python 3.8 compatible: it runs directly on the secondary host
(``python3 -m dbbackup.promote_plan --dir <incoming>``) and prints shell
assignments meant for ``eval``.
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

DUMP_AGE_RE = re.compile(r'^dump-(\d{8}T\d{6})\.sql\.gz\.age$')
BINLOG_AGE_RE = re.compile(r'^(.+)\.(\d{6})\.gz\.age$')


class PlanError(RuntimeError):
    pass


def latest_complete_dump(directory: Path) -> Dict:
    """Newest dump that has both its encrypted data and its meta file."""
    candidates = []
    for p in directory.iterdir():
        m = DUMP_AGE_RE.match(p.name)
        if not m:
            continue
        meta_path = directory / f'dump-{m.group(1)}.meta.json'
        if meta_path.exists():
            candidates.append((m.group(1), p.name, meta_path))
    if not candidates:
        raise PlanError(f'No complete dump (data + meta) found in {directory}')
    stamp, data_name, meta_path = sorted(candidates)[-1]
    try:
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        binlog_file = meta['binlog_file']
        binlog_pos = int(meta['binlog_pos'])
    except (OSError, ValueError, KeyError) as e:
        raise PlanError(f'Unreadable meta {meta_path.name}: {e}')
    return {'data': data_name, 'created': meta.get('created', stamp), 'binlog_file': binlog_file,
            'binlog_pos': binlog_pos, 'database': meta.get('database', '')}


def binlogs_to_replay(directory: Path, start_file: str) -> Dict[str, List]:
    """Archived binlogs to roll the dump forward.

    ``files`` is the CONTIGUOUS run starting at the dump's own binlog: replaying across a
    missing log would silently skip transactions and leave inconsistent data, so everything
    after the first hole is excluded. ``gaps`` lists the missing sequence numbers (up to the
    newest archived log) so the operator knows how much is lost.
    """
    m = re.match(r'^(.+)\.(\d{6})$', start_file)
    if not m:
        raise PlanError(f'Bad binlog name in meta: {start_file!r}')
    base, start_seq = m.group(1), int(m.group(2))
    found = {}
    for p in directory.iterdir():
        bm = BINLOG_AGE_RE.match(p.name)
        if bm and bm.group(1) == base and int(bm.group(2)) >= start_seq:
            found[int(bm.group(2))] = p.name
    gaps: List[str] = []
    contiguous: List[str] = []
    if found:
        broken = False
        for seq in range(start_seq, max(found) + 1):
            if seq in found:
                if not broken:
                    contiguous.append(found[seq])
            else:
                broken = True
                gaps.append(f'{base}.{seq:06d}')
    return {'files': contiguous, 'gaps': gaps}


def build_plan(directory: Path) -> Dict:
    dump = latest_complete_dump(directory)
    logs = binlogs_to_replay(directory, dump['binlog_file'])
    return {**dump, 'binlogs': logs['files'], 'gaps': logs['gaps']}


def to_shell(plan: Dict) -> str:
    lines = [
        f'PLAN_DUMP={shlex.quote(plan["data"])}',
        f'PLAN_CREATED={shlex.quote(str(plan["created"]))}',
        f'PLAN_BINLOG_FILE={shlex.quote(plan["binlog_file"])}',
        f'PLAN_BINLOG_POS={int(plan["binlog_pos"])}',
        f'PLAN_DATABASE={shlex.quote(plan["database"])}',
        'PLAN_BINLOGS=(' + ' '.join(shlex.quote(b) for b in plan['binlogs']) + ')',
        'PLAN_GAPS=(' + ' '.join(shlex.quote(g) for g in plan['gaps']) + ')',
    ]
    return '\n'.join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog='dbbackup.promote_plan')
    ap.add_argument('--dir', required=True)
    args = ap.parse_args(argv)
    try:
        print(to_shell(build_plan(Path(args.dir))))
    except (PlanError, OSError) as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
