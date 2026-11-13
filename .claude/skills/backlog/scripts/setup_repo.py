"""Configuración idempotente del repo para el backlog: etiquetas, ajustes del repositorio y tablero Project.

    setup_repo.py labels                 # crea/actualiza las etiquetas de references/labels.json (renombra enhancement->feature...)
    setup_repo.py settings [--apply]     # muestra (por defecto) o aplica los ajustes: borrar rama al fusionar, solo merge commits
    setup_repo.py project [--apply]      # crea el tablero Project v2 + campos, lo enlaza al repo y guarda su número en config.json

Necesita `gh` autenticado. `project` necesita además el permiso `project` del token: gh auth refresh -h github.com -s project
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
CONFIG = HERE / 'config.json'


def gh(*args, check=True):
    r = subprocess.run(['gh', *args], capture_output=True, text=True, encoding='utf-8')
    if check and r.returncode:
        sys.exit('gh %s failed: %s' % (' '.join(args), r.stderr.strip()))
    return r


def load_config():
    return json.loads(CONFIG.read_text(encoding='utf-8'))


def labels():
    spec = json.loads((HERE / 'references' / 'labels.json').read_text(encoding='utf-8'))
    existing = {l['name'] for l in json.loads(gh('label', 'list', '--limit', '200', '--json', 'name').stdout)}
    for old, new in spec['rename'].items():
        if old in existing and new not in existing:
            gh('label', 'edit', old, '--name', new)
            existing.discard(old)
            existing.add(new)
            print('renamed label %s -> %s' % (old, new))
    for l in spec['labels']:
        verb = 'edit' if l['name'] in existing else 'create'
        gh('label', verb, l['name'], '--color', l['color'], '--description', l['description'])
        print('%s label %s' % ('updated' if verb == 'edit' else 'created', l['name']))


def settings(apply):
    wanted = ['--delete-branch-on-merge', '--enable-merge-commit', '--enable-squash-merge=false', '--enable-rebase-merge=false']
    cur = json.loads(gh('repo', 'view', '--json', 'deleteBranchOnMerge,mergeCommitAllowed,squashMergeAllowed,rebaseMergeAllowed').stdout)
    print('current:', cur)
    print('would apply: gh repo edit', ' '.join(wanted))
    print('(merge commits only keep GitFlow history readable; delete-branch-on-merge removes the head branch after every merged PR)')
    if apply:
        gh('repo', 'edit', *wanted)
        print('applied')
    else:
        print('dry run: pass --apply to change the repository')


def project(apply):
    cfg = load_config()
    if not apply:
        print('would create project "%s" for %s with a Size field; pass --apply' % (cfg['project_title'], cfg['owner']))
        return
    status = gh('auth', 'status', check=False)
    if 'project' not in (status.stdout + status.stderr).split("scopes:")[-1]:
        sys.exit('Missing "project" token scope. Ejecuta: gh auth refresh -h github.com -s project')
    out = json.loads(gh('project', 'create', '--owner', cfg['owner'], '--title', cfg['project_title'], '--format', 'json').stdout)
    num = out['number']
    gh('project', 'link', str(num), '--owner', cfg['owner'], '--repo', cfg['repo'])
    gh('project', 'field-create', str(num), '--owner', cfg['owner'], '--name', 'Size',
       '--data-type', 'SINGLE_SELECT', '--single-select-options', 'XS,S,M,L,XL')
    cfg['project_number'] = num
    cfg['project_url'] = out['url']
    CONFIG.write_text(json.dumps(cfg, indent=2) + '\n', encoding='utf-8')
    print('project #%s created and linked: %s' % (num, out['url']))
    print('Manual UI steps (no API): see references/project-setup.md (Status columns + built-in workflows).')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('what', choices=['labels', 'settings', 'project'])
    p.add_argument('--apply', action='store_true')
    a = p.parse_args()
    {'labels': labels, 'settings': lambda: settings(a.apply), 'project': lambda: project(a.apply)}[a.what]()
