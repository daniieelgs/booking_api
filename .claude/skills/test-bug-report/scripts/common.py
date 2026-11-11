"""Shared helpers for the test-bug-report skill: paths, JSON I/O, running one tier of tests, syncing findings."""
import datetime
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252 and choke on accents
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

SCRIPTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPTS_DIR.parent


def repo_root():
    """The repo root: this skill lives in <root>/.claude/skills/<name>/. Override with TEST_REPORT_ROOT."""
    override = os.environ.get('TEST_REPORT_ROOT')
    candidate = Path(override) if override else SKILL_DIR.parents[2]
    if not (candidate / 'pytest.ini').exists():
        candidate = Path.cwd()
    return candidate


ROOT = repo_root()
REPORT_DIR = ROOT / 'private' / 'reports' / 'tests'
RESULTS_FILE = REPORT_DIR / 'results.json'
FINDINGS_FILE = REPORT_DIR / 'findings.json'
REPORT_FILE = REPORT_DIR / 'report.html'
COMPOSE_FILE = ROOT / 'docker' / 'docker-compose.test.yml'

# One tier = one pytest invocation. `services` needs Docker (MariaDB + Redis) and must run on its own because
# globals.py binds the environment at import time.
TIERS = {
    'unit': {'label': 'Unitarios', 'paths': ['tests/unit'], 'extra': [], 'docker': False},
    'integration': {'label': 'Integración (SQLite)', 'paths': ['tests/integration'], 'extra': [], 'docker': False},
    'services': {'label': 'Servicios reales (Docker)', 'paths': ['tests/integration/services'], 'extra': ['-m', 'services'],
                 'docker': True},
    'backup': {'label': 'Backup', 'paths': ['tests/backup'], 'extra': [], 'docker': False},
}
TIER_ORDER = ['unit', 'integration', 'services', 'backup']


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


def load_json(path, default=None):
    if not Path(path).exists():
        return default
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


def git_info():
    def git(*args):
        try:
            return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, timeout=20).stdout.strip()
        except Exception:
            return ''
    return {'branch': git('rev-parse', '--abbrev-ref', 'HEAD'), 'commit': git('rev-parse', '--short', 'HEAD'),
            'dirty': bool(git('status', '--porcelain'))}


def tier_of(nodeid):
    path = nodeid.replace('\\', '/').split('::')[0]
    if path.startswith('tests/integration/services'):
        return 'services'
    if path.startswith('tests/unit'):
        return 'unit'
    if path.startswith('tests/backup'):
        return 'backup'
    if path.startswith('tests/integration'):
        return 'integration'
    return None


def docker_available():
    try:
        return subprocess.run(['docker', 'info'], capture_output=True, timeout=45).returncode == 0
    except Exception:
        return False


def compose(*args):
    return subprocess.run(['docker', 'compose', '-f', str(COMPOSE_FILE), *args], cwd=ROOT, capture_output=True, text=True)


def run_tier(tier, nodeids=None):
    """Run one tier (or only `nodeids` of it). Returns a dict with tests/duration/deselected/command/note.

    `note` is set when nothing could be measured (Docker down, collection crash...). Never raises for test failures.
    """
    spec = TIERS[tier]
    targets = list(nodeids) if nodeids else spec['paths']
    cmd = [sys.executable, '-m', 'pytest', *targets, '-q', '-W', 'ignore', '-p', 'no:cacheprovider',
           '-p', 'pytest_json_plugin', *spec['extra']]
    printable = 'python -m pytest ' + ' '.join(targets if len(targets) <= 3 else targets[:3] + ['...']) \
        + (' ' + ' '.join(spec['extra']) if spec['extra'] else '')
    outcome = {'command': printable, 'tests': {}, 'deselected': 0, 'duration': 0.0, 'note': None}

    env = {**os.environ, 'PYTHONPATH': os.pathsep.join([str(SCRIPTS_DIR), os.environ.get('PYTHONPATH', '')]),
           'PYTHONIOENCODING': 'utf-8'}
    started_stack = False
    if spec['docker']:
        if not docker_available():
            outcome['note'] = 'Docker no responde: no se han podido levantar MariaDB y Redis.'
            return outcome
        up = compose('up', '-d', '--wait')
        if up.returncode != 0:
            outcome['note'] = 'docker compose up falló: ' + (up.stderr or up.stdout)[-400:]
            compose('down', '-v', '--remove-orphans')
            return outcome
        started_stack = True
        env['RUN_INTEGRATION_TESTS'] = '1'

    handle, report_path = tempfile.mkstemp(suffix='.json')
    os.close(handle)
    env['PYTEST_JSON_REPORT'] = report_path
    try:
        proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
        data = load_json(report_path, {}) if os.path.getsize(report_path) else {}
        outcome['tests'] = data.get('tests', {})
        outcome['deselected'] = data.get('deselected', 0)
        outcome['duration'] = data.get('duration', 0.0)
        if not outcome['tests']:
            outcome['note'] = 'pytest no devolvió resultados (código %s): %s' % (proc.returncode, (proc.stdout + proc.stderr)[-500:])
        outcome['stdout_tail'] = proc.stdout[-1500:]
    finally:
        os.unlink(report_path)
        if started_stack:
            compose('down', '-v', '--remove-orphans')
    return outcome


def recount(tier_data):
    """Recompute counts from the per-test outcomes."""
    tests = tier_data.get('tests', {})
    counts = {'passed': 0, 'failed': 0, 'skipped': 0}
    for outcome in tests.values():
        if outcome in ('passed', 'xpassed'):
            counts['passed'] += 1
        elif outcome in ('failed', 'error'):
            counts['failed'] += 1
        else:
            counts['skipped'] += 1
    counts['total'] = len(tests)
    counts['deselected'] = tier_data.get('counts', {}).get('deselected', 0)
    tier_data['counts'] = counts
    return counts


def merge_tier(results, tier, run, partial=False):
    """Fold a run_tier() result into results.json. A full run replaces the tier; a partial run updates only its tests."""
    entry = results.setdefault('tiers', {}).setdefault(tier, {'label': TIERS[tier]['label'], 'tests': {}, 'failures': {}})
    entry['label'] = TIERS[tier]['label']
    if run['note'] and not run['tests']:
        previous_counts = entry.get('counts')
        entry['status'] = 'not_run'
        entry['reason'] = run['note']
        if previous_counts and entry.get('measured_at'):
            entry['stale'] = True  # keep the last measured numbers, clearly flagged
        return entry
    if not partial:
        entry['tests'], entry['failures'] = {}, {}
        entry['counts'] = {'deselected': run['deselected']}
        entry['command'] = run['command']
        entry['duration_seconds'] = run['duration']
    for nodeid, info in run['tests'].items():
        entry['tests'][nodeid] = info['outcome']
        entry['failures'].pop(nodeid, None)
        if info['outcome'] in ('failed', 'error'):
            entry['failures'][nodeid] = {k: v for k, v in info.items() if k not in ('outcome', 'duration')}
    entry['status'] = 'ran'
    entry['stale'] = False
    entry.pop('reason', None)
    entry['measured_at'] = now_iso()
    recount(entry)
    return entry


def all_outcomes(results):
    merged = {}
    for tier in results.get('tiers', {}).values():
        merged.update(tier.get('tests', {}))
    return merged


def failure_detail(results, nodeid):
    tier = results.get('tiers', {}).get(tier_of(nodeid) or '', {})
    return tier.get('failures', {}).get(nodeid)


def sync_findings(findings, results, source):
    """Update finding statuses from the outcomes in results.json. Returns (changes, unanalyzed failing nodeids)."""
    outcomes = all_outcomes(results)
    changes = []
    referenced = set()
    for finding in findings.get('findings', []):
        tests = finding.get('tests', [])
        referenced.update(tests)
        if not tests or finding.get('status') not in ('open', 'fixed'):
            continue
        known = [outcomes[t] for t in tests if t in outcomes]
        if len(known) != len(tests):
            continue  # some test was not measured in this run: do not guess
        failing = [t for t in tests if outcomes[t] in ('failed', 'error')]
        if not failing and finding['status'] == 'open':
            finding['status'] = 'fixed'
            finding['status_updated_at'] = now_iso()
            finding['latest_failure'] = None
            finding.setdefault('history', []).append({'at': now_iso(), 'event': 'Todos sus tests pasan (%s): marcado como arreglado' % source})
            changes.append((finding['id'], 'open', 'fixed'))
        elif failing:
            detail = failure_detail(results, failing[0]) or {}
            finding['latest_failure'] = {'test': failing[0], 'message': detail.get('message'),
                                         **{k: detail[k] for k in ('test_path', 'test_line', 'code_path', 'code_line',
                                                                   'crash_path', 'crash_line') if k in detail},
                                         'at': now_iso()}
            if finding['status'] == 'fixed':
                finding['status'] = 'open'
                finding['status_updated_at'] = now_iso()
                finding.setdefault('history', []).append({'at': now_iso(), 'event': 'Vuelve a fallar (%s): reabierto' % source})
                changes.append((finding['id'], 'fixed', 'open'))
    unanalyzed = sorted(t for t, o in outcomes.items() if o in ('failed', 'error') and t not in referenced)
    return changes, unanalyzed


def print_summary(results):
    print('\nResumen')
    total = passed = failed = 0
    for name in TIER_ORDER:
        tier = results.get('tiers', {}).get(name)
        if not tier:
            continue
        counts = tier.get('counts', {})
        flag = '' if tier.get('status') == 'ran' else '  [no medido ahora: %s]' % ('dato anterior' if tier.get('stale') else tier.get('reason', ''))
        print('  %-28s total %-4s pasan %-4s fallan %-3s%s' % (tier['label'], counts.get('total', '-'), counts.get('passed', '-'),
                                                             counts.get('failed', '-'), flag))
        total += counts.get('total', 0)
        passed += counts.get('passed', 0)
        failed += counts.get('failed', 0)
    if total:
        print('  %-28s total %-4s pasan %-4s (%.2f%%) fallan %-3s (%.2f%%)' % ('TOTAL', total, passed, 100 * passed / total, failed,
                                                                             100 * failed / total))
