"""Docker HEALTHCHECK: only verifies that the service loop is alive (status file fresh).

Backup *quality* problems (stale dump, unreachable secondary) are reported through
Uptime Kuma instead; failing the container healthcheck for them would make autoheal
restart the container in a loop without fixing anything.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from .heartbeat import STATUS_FILE
from .util import parse_iso, read_json

MAX_AGE_SECONDS = 15 * 60


def is_alive(backup_dir: str, now: Optional[datetime] = None, max_age: int = MAX_AGE_SECONDS) -> bool:
    now = now or datetime.now()
    status = read_json(Path(backup_dir) / 'state' / STATUS_FILE)
    if not isinstance(status, dict):
        return False
    updated = parse_iso(status.get('updated'))
    if updated is None:
        return False
    return (now - updated).total_seconds() <= max_age


def main() -> int:
    import os
    return 0 if is_alive(os.environ.get('BACKUP_DIR', '/backups')) else 1


if __name__ == '__main__':
    sys.exit(main())
