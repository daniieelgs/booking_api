"""Comprobación de solo lectura de si una release está lista: origin/develop frente a origin/master.

    release_check.py            # informe de preparación
    release_check.py --notes    # además, notas de release en Markdown (PR fusionadas por tipo, issues enlazadas)

Necesita `git` y `gh` (autenticado). Código de salida 1 si encuentra un problema bloqueante.
"""
import argparse
import json
import re
import subprocess
import sys

REPO = 'daniieelgs/booking_api'


def run(*cmd, check=True):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    if check and r.returncode:
        sys.exit('%s failed: %s' % (' '.join(cmd), r.stderr.strip()))
    return r.stdout.strip()


def version_at(ref):
    m = re.search(r"^VERSION\s*=\s*'([^']+)'", run('git', 'show', ref + ':globals.py'), re.M)
    return m.group(1) if m else None


def semver(v):
    return tuple(int(x) for x in re.findall(r'\d+', v or '0.0.0')[:3])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--notes', action='store_true')
    args = ap.parse_args()
    run('git', 'fetch', 'origin', '--quiet')
    problems = []

    vd, vm = version_at('origin/develop'), version_at('origin/master')
    print('VERSION: develop %s, master %s' % (vd, vm))
    if semver(vd) <= semver(vm):
        problems.append('VERSION on develop (%s) is not higher than master (%s): bump it in globals.py' % (vd, vm))

    behind = run('git', 'log', '--oneline', '--no-merges', 'origin/develop..origin/master').splitlines()
    ahead = run('git', 'log', '--oneline', 'origin/master..origin/develop').splitlines()
    print('develop has %d commits not in master; master has %d commits not in develop' % (len(ahead), len(behind)))
    if behind:
        problems.append('master has %d commit(s) missing in develop (hotfix not merged back?)' % len(behind))
    if not ahead:
        problems.append('nothing to release: develop == master')

    prs = []
    for line in run('git', 'log', '--merges', '--format=%s', 'origin/master..origin/develop').splitlines():
        m = re.search(r'Merge pull request #(\d+)', line)
        if m:
            prs.append(int(m.group(1)))
    infos = []
    for n in sorted(set(prs)):
        d = json.loads(run('gh', 'pr', 'view', str(n), '--repo', REPO, '--json', 'number,title,body,labels,url'))
        issues = sorted(set(int(x) for x in re.findall(r'(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)', d['body'] or '', re.I)))
        infos.append((d, issues))
    print('merged PRs in this release: %s' % (', '.join('#%d' % d['number'] for d, _ in infos) or 'none'))

    runs = json.loads(run('gh', 'run', 'list', '--repo', REPO, '--branch', 'develop', '--limit', '3',
                          '--json', 'name,conclusion,status,headSha,url', check=False) or '[]')
    for r in runs:
        print('CI develop: %s %s/%s' % (r['name'], r['status'], r['conclusion']))
    if runs and runs[0].get('conclusion') not in ('success', None):
        problems.append('latest CI run on develop is %s' % runs[0]['conclusion'])

    for label in ('P0', 'P1'):
        bugs = json.loads(run('gh', 'issue', 'list', '--repo', REPO, '--state', 'open', '--label', 'bug', '--label', label,
                              '--json', 'number,title'))
        for b in bugs:
            msg = 'open %s bug #%d: %s' % (label, b['number'], b['title'])
            print(msg)
            if label == 'P0':
                problems.append(msg)

    if args.notes:
        groups = {'Features': [], 'Fixes': [], 'Other': []}
        for d, issues in infos:
            names = {l['name'] for l in d['labels']}
            t = d['title'].lower()
            key = 'Features' if t.startswith('feat') else 'Fixes' if t.startswith('fix') or 'bug' in names else 'Other'
            groups[key].append('- %s (#%d%s)' % (d['title'], d['number'], ''.join(', closes #%d' % i for i in issues)))
        print('\n---- release notes ----\n## Release v%s\n' % vd)
        for k, v in groups.items():
            if v:
                print('### %s\n%s\n' % (k, '\n'.join(v)))
        print('### Deployment impact\n_Aggregate from the PRs: restarts, migrations, image rebuild, new env vars._')

    print()
    if problems:
        print('NOT READY:')
        for p in problems:
            print(' -', p)
        sys.exit(1)
    print('Ready: no blocking problems found (still confirm the secondary was verified).')


if __name__ == '__main__':
    main()
