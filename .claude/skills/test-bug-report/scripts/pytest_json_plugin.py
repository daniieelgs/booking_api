"""Tiny pytest plugin (no dependencies): writes one JSON file with the outcome of every test.

Usage (done by run_tests.py / recheck.py):
    PYTEST_JSON_REPORT=out.json python -m pytest -p pytest_json_plugin ...

Output:
    {"tests": {nodeid: {"outcome": ..., "duration": ...,
                        # only for failed/error:
                        "message": ..., "crash_path": ..., "crash_line": ..., "traceback": ...}},
     "deselected": N, "duration": seconds}
"""
import json
import os
import time

_results = {}
_deselected = 0
_started = time.time()

_RANK = {'passed': 0, 'skipped': 1, 'xfailed': 1, 'xpassed': 2, 'failed': 3, 'error': 3}


def _relative(path):
    path = str(path).replace('\\', '/')
    root = os.getcwd().replace('\\', '/').rstrip('/') + '/'
    return path[len(root):] if path.startswith(root) else path


def _frames(longrepr):
    """Where it failed, in terms useful for a human: the last frame inside tests/ (`test_path:test_line`) and the
    deepest frame in the application code (`code_path:code_line`), skipping unittest/pytest/site-packages frames.
    `crash_path` alone usually points at unittest's assert helper or a library."""
    found = {}
    entries = getattr(getattr(longrepr, 'reprtraceback', None), 'reprentries', None) or []
    for entry in entries:
        location = getattr(entry, 'reprfileloc', None)
        if location is None:
            continue
        path = _relative(location.path)
        if path.startswith('/') or ':' in path[:3] or '.venv' in path or 'site-packages' in path:
            continue  # outside the repo (stdlib, libraries)
        key = 'test' if path.startswith('tests/') else 'code'
        found[key + '_path'], found[key + '_line'] = path, location.lineno
    return found


def _store(nodeid, outcome, duration=0.0, report=None):
    entry = {'outcome': outcome, 'duration': round(duration, 4)}
    if outcome in ('failed', 'error') and report is not None:
        longrepr = getattr(report, 'longrepr', None)
        crash = getattr(longrepr, 'reprcrash', None)
        text = getattr(report, 'longreprtext', None) or str(longrepr)
        entry['message'] = (crash.message if crash else text)[:1500]
        if crash:
            entry['crash_path'] = str(crash.path).replace('\\', '/')
            entry['crash_line'] = crash.lineno
        entry['traceback'] = text[-6000:]
        entry.update(_frames(longrepr))
    previous = _results.get(nodeid)
    if previous is None or _RANK[outcome] > _RANK[previous['outcome']]:
        if previous is not None:
            entry['duration'] = round(entry['duration'] + previous['duration'], 4)
        _results[nodeid] = entry
    else:
        previous['duration'] = round(previous['duration'] + duration, 4)


def pytest_deselected(items):
    global _deselected
    _deselected += len(items)


def pytest_runtest_logreport(report):
    if report.when == 'call':
        if hasattr(report, 'wasxfail'):
            outcome = 'xfailed' if report.skipped else 'xpassed'
        else:
            outcome = report.outcome
        _store(report.nodeid, outcome, report.duration, report)
    elif report.outcome == 'failed':
        _store(report.nodeid, 'error', report.duration, report)
    elif report.outcome == 'skipped':
        _store(report.nodeid, 'skipped', report.duration)


def pytest_collectreport(report):
    # import errors: the whole module fails to collect and none of its tests exist
    if report.failed:
        _store(report.nodeid or 'collection', 'error', 0.0, report)


def pytest_sessionfinish(session):
    path = os.environ.get('PYTEST_JSON_REPORT')
    if not path:
        return
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'tests': _results, 'deselected': _deselected, 'duration': round(time.time() - _started, 2)}, f)
