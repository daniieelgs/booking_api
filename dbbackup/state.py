from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from .util import atomic_write_json, iso, parse_iso, read_json

MAX_ARCHIVED_NAMES = 500


class State:
    """Small JSON file that survives container restarts.

    Keys: last_dump_attempt, last_dump_ok, last_binlog_ship, last_send_attempt,
    last_send_ok, last_heartbeat (ISO datetimes, naive local time), last_error,
    archived_binlogs (list of server binlog names already archived) and
    sent (remote file name -> ISO datetime it reached the secondary).
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        data = read_json(self.path, {})
        self.data = data if isinstance(data, dict) else {}
        self.data.setdefault('sent', {})
        self.data.setdefault('archived_binlogs', [])

    def get_dt(self, key: str) -> Optional[datetime]:
        return parse_iso(self.data.get(key))

    def set_dt(self, key: str, value: Optional[datetime]) -> None:
        self.data[key] = iso(value) if value else None

    @property
    def sent(self) -> dict:
        return self.data['sent']

    @property
    def archived_binlogs(self) -> list:
        return self.data['archived_binlogs']

    def mark_sent(self, remote_name: str, when: datetime) -> None:
        self.data['sent'][remote_name] = iso(when)

    def mark_archived(self, binlog_name: str) -> None:
        names = self.data['archived_binlogs']
        if binlog_name not in names:
            names.append(binlog_name)
        del names[:-MAX_ARCHIVED_NAMES]

    def set_error(self, message: Optional[str], when: Optional[datetime] = None) -> None:
        self.data['last_error'] = (f'{iso(when)} {message}' if when and message else message)

    def save(self) -> None:
        atomic_write_json(self.path, self.data)
