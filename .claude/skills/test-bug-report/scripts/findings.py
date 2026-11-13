"""Read and edit findings.json without opening the HTML or running any test.

    findings.py list [--status open|fixed|wontfix] [--tier unit|integration|services|backup] [--size small|medium|discuss]
    findings.py show F-003            # the whole finding as JSON: tests, root cause, evidence, files, suggested fix
    findings.py status F-011 wontfix --note "decidido con el equipo"
    findings.py add path/to/finding.json   # append (or replace by id) a finding written by hand

Backlog de GitHub (necesita `gh`; ver .claude/skills/backlog):
    findings.py sync-backlog               # lee las issues `bug`: enlaza hallazgos con su issue y añade el resto como kind "backlog" (B-<n>)
    findings.py publish F-003 --area email [--dry-run]   # crea la issue de GitHub de un hallazgo (PREGUNTA ANTES AL USUARIO)
    findings.py link F-003 123             # asocia un número de issue existente a un hallazgo
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from common import FINDINGS_FILE, load_json, now_iso, save_json


BACKLOG = Path(__file__).resolve().parents[2] / 'backlog'
MARKER = re.compile(r'<!--\s*finding:\s*(F-\d+)\s*-->')
PRIORITY = {'critical': 'P0', 'high': 'P1', 'medium': 'P2', 'low': 'P3'}
SEVERITY = {v: k for k, v in PRIORITY.items()}


def gh_json(*args):
    r = subprocess.run(['gh', *args], capture_output=True, text=True, encoding='utf-8')
    if r.returncode:
        sys.exit('gh failed: ' + r.stderr.strip())
    return json.loads(r.stdout or 'null')


def backlog_repo():
    return json.loads((BACKLOG / 'config.json').read_text(encoding='utf-8'))['repo']


def issue_ref(issue):
    return {'number': issue['number'], 'url': issue['url'], 'state': issue['state'].lower()}


def sync_backlog(data):
    """Link findings to GitHub issues and mirror the open backlog bugs into findings.json (kind "backlog")."""
    issues = gh_json('issue', 'list', '--repo', backlog_repo(), '--state', 'all', '--label', 'bug', '--limit', '500',
                     '--json', 'number,title,url,state,labels,body')
    items = data['findings']
    by_id = {f['id']: f for f in items}
    by_number = {i['number']: i for i in issues}
    linked = set()
    for i in issues:
        m = MARKER.search(i.get('body') or '')
        if m and m.group(1) in by_id:
            by_id[m.group(1)]['issue'] = issue_ref(i)
            linked.add(i['number'])
    for f in items:  # linked by hand (findings.py link)
        ref = f.get('issue')
        if ref and ref['number'] in by_number:
            f['issue'] = issue_ref(by_number[ref['number']])
            linked.add(ref['number'])
    items[:] = [f for f in items if f.get('kind') != 'backlog']
    added = 0
    for i in issues:
        if i['number'] in linked or i['state'] == 'CLOSED':
            continue
        names = [l['name'] for l in i['labels']]
        discuss = 'needs-discussion' in names
        items.append({
            'id': 'B-%s' % i['number'], 'kind': 'backlog', 'tier': None, 'tests': [], 'status': 'open',
            'severity': next((SEVERITY[n] for n in names if n in SEVERITY), 'medium'), 'title': i['title'],
            'bug_description': 'Bug del backlog de GitHub; este reporte aún no tiene un test que lo reproduzca.',
            'issue': issue_ref(i), 'change_size': 'discuss' if discuss else 'medium',
            'discuss_reason': 'Marcado needs-discussion en GitHub.' if discuss else None,
            'history': [{'at': now_iso(), 'event': 'Importado del backlog de GitHub'}]})
        added += 1
    items.sort(key=lambda f: (f['id'][0], int(re.sub(r'\D', '', f['id']) or 0)))
    return '%d findings linked to an issue, %d open backlog bugs added as kind "backlog"' % (len(linked), added)


def finding_issue_body(f):
    evidence = '\n\n'.join('**%s**\n```\n%s\n```' % (e.get('type', ''), (e.get('text') or '')[:1500])
                           for e in f.get('evidence', [])[:3])
    tests = '\n'.join('- `%s`' % t for t in f.get('tests', [])) or '- (no test fails for this one: found by code analysis)'
    fix = f.get('suggested_fix') or {}
    files = '\n'.join('- `%s:%s` %s' % (a['path'], a['lines'], a.get('note', '')) for a in f.get('affected_files', []))
    steps = '\n'.join('- [ ] %s' % s for s in fix.get('steps', []))
    discuss = ('### Discussion needed\n%s' % f['discuss_reason']) if f.get('discuss_reason') else ''
    return '\n\n'.join(filter(None, [
        '<!-- finding: %s -->' % f['id'],
        '### Summary\n%s' % f['bug_description'],
        '### Steps to reproduce / evidence\nFailing tests (re-run with `recheck.py --finding %s`):\n%s\n\n%s' % (f['id'], tests, evidence),
        '### Expected vs actual behaviour\n%s\n\nActual: %s' % (f.get('test_description') or 'See summary.', f['bug_description']),
        '### Root cause / affected code\n%s\n\n%s' % (f.get('root_cause') or 'Not determined.', files),
        '### Proposed fix and how to verify\n%s\n\n%s\n\nVerify: the tests above must pass.' % (fix.get('summary', ''), steps),
        discuss]))


def publish(data, args):
    f = next((x for x in data['findings'] if x['id'] == args.id), None)
    if not f:
        sys.exit('No existe el hallazgo %s' % args.id)
    if f.get('issue'):
        sys.exit('%s ya tiene la issue #%s' % (f['id'], f['issue']['number']))
    out = FINDINGS_FILE.parent / 'issue_bodies'
    out.mkdir(exist_ok=True)
    body = out / ('%s.md' % f['id'])
    body.write_text(finding_issue_body(f), encoding='utf-8')
    cmd = [sys.executable, str(BACKLOG / 'scripts' / 'issue.py'), 'create', '--type', 'bug', '--title', f['title'],
           '--body-file', str(body), '--priority', PRIORITY.get(f.get('severity'), 'P2'), '--area', args.area,
           '--label', 'from-test-report']
    if f.get('change_size') == 'discuss':
        cmd += ['--label', 'needs-discussion']
    if args.dry_run:
        cmd.append('--dry-run')
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', env={**os.environ, 'PYTHONUTF8': '1'})
    print((r.stdout or '').strip() or (r.stderr or '').strip())
    if r.returncode or args.dry_run:
        sys.exit(r.returncode)
    url = r.stdout.strip().splitlines()[0]
    f['issue'] = {'number': int(url.rstrip('/').split('/')[-1]), 'url': url, 'state': 'open'}
    f.setdefault('history', []).append({'at': now_iso(), 'event': 'Publicado en GitHub: %s' % url})


def load():
    data = load_json(FINDINGS_FILE)
    if data is None:
        sys.exit('No existe %s. Ejecuta primero el análisis (ver SKILL.md).' % FINDINGS_FILE)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('list')
    p.add_argument('--status')
    p.add_argument('--tier')
    p.add_argument('--size')
    p = sub.add_parser('show')
    p.add_argument('id')
    p = sub.add_parser('status')
    p.add_argument('id')
    p.add_argument('status', choices=['open', 'fixed', 'wontfix'])
    p.add_argument('--note', default='')
    p = sub.add_parser('add')
    p.add_argument('file')
    sub.add_parser('sync-backlog')
    p = sub.add_parser('publish')
    p.add_argument('id')
    p.add_argument('--area', required=True, help='api, bookings, email, worker-celery, redis, database, backups, auth-security, infra-docker, tests-ci, docs')
    p.add_argument('--dry-run', action='store_true')
    p = sub.add_parser('link')
    p.add_argument('id')
    p.add_argument('number', type=int)
    args = parser.parse_args()

    data = load() if args.cmd not in ('add', 'sync-backlog') else (load_json(FINDINGS_FILE) or {'schema': 1, 'findings': []})
    items = data['findings']

    if args.cmd == 'list':
        for f in items:
            if args.status and f.get('status') != args.status:
                continue
            if args.tier and f.get('tier') != args.tier:
                continue
            if args.size and f.get('change_size') != args.size:
                continue
            print('%-7s %-7s %-12s %-8s %-8s %-6s %s' % (
                f['id'], f.get('status'), f.get('tier') or f.get('kind'), f.get('severity'), f.get('change_size'),
                ('#%s' % f['issue']['number']) if f.get('issue') else '-', f['title']))
        return

    if args.cmd == 'show':
        found = [f for f in items if f['id'] == args.id]
        if not found:
            sys.exit('No existe el hallazgo %s' % args.id)
        print(json.dumps(found[0], ensure_ascii=False, indent=2))
        return

    if args.cmd == 'status':
        found = [f for f in items if f['id'] == args.id]
        if not found:
            sys.exit('No existe el hallazgo %s' % args.id)
        f = found[0]
        f['status'] = args.status
        f['status_updated_at'] = now_iso()
        f.setdefault('history', []).append({'at': now_iso(), 'event': 'Estado manual: %s. %s' % (args.status, args.note)})
    elif args.cmd == 'sync-backlog':
        data = load_json(FINDINGS_FILE) or {'schema': 1, 'findings': []}
        print(sync_backlog(data))
    elif args.cmd == 'publish':
        publish(data, args)
    elif args.cmd == 'link':
        f = next((x for x in items if x['id'] == args.id), None)
        if not f:
            sys.exit('No existe el hallazgo %s' % args.id)
        f['issue'] = {'number': args.number, 'url': 'https://github.com/%s/issues/%s' % (backlog_repo(), args.number),
                      'state': 'open'}
    elif args.cmd == 'add':
        with open(args.file, encoding='utf-8') as fh:
            new = json.load(fh)
        for item in (new if isinstance(new, list) else [new]):
            item.setdefault('status', 'open')
            item.setdefault('history', [{'at': now_iso(), 'event': 'Hallazgo creado'}])
            items[:] = [f for f in items if f['id'] != item['id']] + [item]
        items.sort(key=lambda f: f['id'])

    data['updated_at'] = now_iso()
    save_json(FINDINGS_FILE, data)
    print('findings.json actualizado. Regenera el HTML con build_report.py si lo vas a mirar.')


if __name__ == '__main__':
    main()
