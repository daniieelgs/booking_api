"""Create and audit backlog issues so every one is fully specified.

    issue.py create --type bug|feature|task --title "..." --body-file body.md --priority P2 --area email
                    [--milestone v1.2.0] [--label needs-discussion ...] [--dry-run]
    issue.py audit                      # list open issues that are badly specified (missing labels/sections)

The body uses the same `### Heading` sections as the issue forms in .github/ISSUE_TEMPLATE, so issues created from
the web form and from here look identical. `create` refuses a body that lacks the required sections or looks like
it contains a secret (the repository is public).
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

CONFIG = json.loads((Path(__file__).resolve().parent.parent / 'config.json').read_text(encoding='utf-8'))
REQUIRED = {
    'bug': ['Summary', 'Steps to reproduce / evidence', 'Expected vs actual behaviour'],
    'feature': ['Problem / goal', 'Proposed solution and scope', 'Acceptance criteria'],
    'task': ['Context and goal', 'Plan / checklist', 'Definition of done'],
}
PRIORITIES = ['P0', 'P1', 'P2', 'P3']
SECRET_RE = re.compile(r'(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*\S{6,}', re.I)


def gh(*args):
    cmd = ['gh', *args]
    if args[0] == 'issue':
        cmd += ['--repo', CONFIG['repo']]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    if r.returncode:
        sys.exit('gh failed: ' + r.stderr.strip())
    return r.stdout.strip()


def sections(body):
    return {m.group(1).strip(): m.group(2).strip()
            for m in re.finditer(r'^###\s+(.+?)\n(.*?)(?=^###\s|\Z)', body, re.S | re.M)}


def create(a):
    body = Path(a.body_file).read_text(encoding='utf-8')
    found = sections(body)
    missing = [h for h in REQUIRED[a.type]
               if not found.get(h) or found[h].lower() in ('_no response_', 'tbd', 'todo')]
    if missing:
        sys.exit('Body is missing required sections for a %s: %s' % (a.type, ', '.join(missing)))
    if SECRET_RE.search(body):
        sys.exit('Body looks like it contains a secret (public repo). Redact it and retry.')
    labels = [a.type, a.priority, 'area:' + a.area] + (a.label or [])
    cmd = ['issue', 'create', '--title', a.title, '--body-file', a.body_file]
    for label in labels:
        cmd += ['--label', label]
    if a.milestone:
        cmd += ['--milestone', a.milestone]
    if a.dry_run:
        print('DRY RUN: gh', ' '.join(cmd))
        return
    url = gh(*cmd)
    print(url)
    if CONFIG.get('project_number'):
        gh('project', 'item-add', str(CONFIG['project_number']), '--owner', CONFIG['owner'], '--url', url)


def audit(_):
    issues = json.loads(gh('issue', 'list', '--state', 'open', '--limit', '300',
                           '--json', 'number,title,labels,milestone,body'))
    bad = 0
    for i in issues:
        names = {l['name'] for l in i['labels']}
        kind = next((t for t in REQUIRED if t in names), None)
        problems = []
        if not kind:
            problems.append('no type label (bug/feature/task)')
        if not names & set(PRIORITIES):
            problems.append('no priority')
        if not any(n.startswith('area:') for n in names):
            problems.append('no area')
        if kind:
            found = sections(i['body'] or '')
            miss = [h for h in REQUIRED[kind] if not found.get(h)]
            if miss:
                problems.append('missing sections: ' + ', '.join(miss))
        if problems:
            bad += 1
            print('#%-4s %s\n      - %s' % (i['number'], i['title'], '\n      - '.join(problems)))
    print('%d/%d open issues need attention' % (bad, len(issues)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('create')
    c.add_argument('--type', choices=list(REQUIRED), required=True)
    c.add_argument('--title', required=True)
    c.add_argument('--body-file', required=True)
    c.add_argument('--priority', choices=PRIORITIES, default='P2')
    c.add_argument('--area', required=True)
    c.add_argument('--milestone')
    c.add_argument('--label', action='append')
    c.add_argument('--dry-run', action='store_true')
    sub.add_parser('audit')
    a = p.parse_args()
    {'create': create, 'audit': audit}[a.cmd](a)
