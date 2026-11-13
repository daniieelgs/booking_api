"""Comprobador de coherencia de la documentación (solo lectura). Ver ../SKILL.md.

    check_docs.py [--strict]
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CLAUDE_BUDGET = 18000
TOP = ('resources', 'helpers', 'models', 'docs', 'tests', 'scripts', 'docker', 'celery_app', 'dbbackup', 'db',
       '.claude', '.github', 'private', 'public', 'migrations', 'instance')
ROOT_FILES = {'app.py', 'globals.py', 'config.py', 'default_config.py', 'schema.py', 'db.py', 'access.py', 'wsgi.py',
              'make_celery.py', 'conftest.py', 'pytest.ini', 'requirements.txt', 'changelog.md', 'CLAUDE.md',
              'build.sh', 'build.ps1', '.gitignore', '.gitattributes', '.env.example'}
IGNORED = ('private/', 'public/', '.env', 'docker/.env', 'db/.env', '.claude/servers.local.md', 'migrations/', 'instance/', '.venv/')
PATH_RE = re.compile(r'`([^`\s]+)`')
LINK_RE = re.compile(r'\[[^\]]*\]\(([^)\s#]+)(?:#[^)]*)?\)')


def doc_files():
    files = [ROOT / 'CLAUDE.md']
    files += sorted((ROOT / 'docs').rglob('*.md'))
    files += sorted((ROOT / '.claude' / 'agents').glob('*.md'))
    files += sorted((ROOT / '.claude' / 'skills').rglob('*.md'))
    files += sorted((ROOT / '.github').rglob('*.md'))
    return [f for f in files if f.exists() and 'servers.local' not in f.name]


def looks_like_repo_path(tok):
    if any(c in tok for c in '<>*{}$|=,;()') or tok.startswith(('http', '/', '~', '-', '.venv')):
        return False
    tok = tok.split(':')[0].rstrip('.,')
    return tok in ROOT_FILES or tok.split('/')[0] in TOP and '/' in tok


def main():
    strict = '--strict' in sys.argv
    errors, warnings = [], []
    claude = ROOT / 'CLAUDE.md'
    text = claude.read_text(encoding='utf-8')
    size = len(text.encode('utf-8'))
    if size > CLAUDE_BUDGET:
        errors.append('CLAUDE.md is %d bytes, budget %d: move detail to docs/, an agent/skill or the backlog' % (size, CLAUDE_BUDGET))
    if re.search(r'^#+\s.*(roadmap|pending tasks)', text, re.I | re.M):
        errors.append('CLAUDE.md has a roadmap/pending-tasks section: pending work belongs in GitHub Issues')

    version = re.search(r"^VERSION\s*=\s*'([^']+)'", (ROOT / 'globals.py').read_text(encoding='utf-8'), re.M)
    for f in doc_files():
        rel = f.relative_to(ROOT).as_posix()
        body = f.read_text(encoding='utf-8')
        for tok in set(PATH_RE.findall(body)):
            if not looks_like_repo_path(tok):
                continue
            p = tok.split(':')[0].rstrip('.,')
            if p.startswith(IGNORED) or any(p == i.rstrip('/') for i in IGNORED):
                continue
            skill_root = next((q for q in [f.parent, *f.parents] if (q / 'SKILL.md').exists()), f.parent)
            if not any((base / p).exists() for base in (ROOT, f.parent, skill_root)):
                errors.append('%s: path `%s` does not exist' % (rel, tok))
        for link in set(LINK_RE.findall(body)):
            if link.startswith(('http', 'mailto:')):
                continue
            if not (f.parent / link).resolve().exists():
                errors.append('%s: link (%s) does not resolve' % (rel, link))
        for m in re.finditer(r'python\s+(\.claude/[\w./-]+\.py)', body):
            if not (ROOT / m.group(1)).exists():
                errors.append('%s: script %s does not exist' % (rel, m.group(1)))
        if version:
            for m in re.finditer(r'\bVERSION\b[^\n]{0,40}?(\d+\.\d+\.\d+)', body):
                if m.group(1) != version.group(1):
                    warnings.append('%s: mentions version %s, globals.py has %s' % (rel, m.group(1), version.group(1)))

    for kind, pattern, namefn in (('agent', '.claude/agents/*.md', lambda p: p.stem),
                                  ('skill', '.claude/skills/*/SKILL.md', lambda p: p.parent.name)):
        for f in sorted(ROOT.glob(pattern)):
            m = re.match(r'---\n(.*?)\n---', f.read_text(encoding='utf-8').replace('\r\n', '\n'), re.S)
            rel = f.relative_to(ROOT).as_posix()
            if not m:
                errors.append('%s: missing frontmatter' % rel)
                continue
            meta = dict(re.findall(r'^(\w+):\s*(.*)$', m.group(1), re.M))
            if not meta.get('description'):
                errors.append('%s: frontmatter without description' % rel)
            if meta.get('name') != namefn(f):
                errors.append('%s: frontmatter name %r differs from %r' % (rel, meta.get('name'), namefn(f)))

    for w in warnings:
        print('warning:', w)
    for e in errors:
        print('ERROR:', e)
    print('CLAUDE.md: %d bytes (budget %d). %d error(s), %d warning(s).' % (size, CLAUDE_BUDGET, len(errors), len(warnings)))
    sys.exit(1 if errors or (strict and warnings) else 0)


if __name__ == '__main__':
    main()
