"""Guard for the write-tests skill: fails if any test marks an expected failure, warns about weak tests.

    python .claude/skills/write-tests/scripts/check_tests.py [paths...]      # default: the whole tests/ folder

Errors (exit code 1): pytest.mark.xfail, pytest.xfail(...), unittest.expectedFailure (and any import/alias of them).
The project rule is that a failing test stays red: an expected-failure marker hides a real bug behind a green suite.

Warnings (exit code stays 0, but read them):
  * skip markers/calls other than the conftest.py gating of the services tier: a skipped test is a test that never runs;
  * test functions without any assertion (assert, self.assert*, pytest.raises, mock .assert_*...), which cannot fail;
  * `tests/__init__.py` not empty (it must stay empty so the backup tests do not import the Flask app).
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
FORBIDDEN_ATTRS = {'xfail', 'expectedFailure'}
SKIP_ATTRS = {'skip', 'skipIf', 'skipUnless', 'importorskip'}


def attr_chain(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return list(reversed(parts))


def has_assertion(func):
    """True if the test can fail: assert statements, self.assert*/mock .assert_*, pytest.raises/warns/fail, assertRaises."""
    for node in ast.walk(func):
        if isinstance(node, ast.Assert):
            return True
        if isinstance(node, ast.Call):
            chain = attr_chain(node.func)
            name = chain[-1] if chain else ''
            if name.startswith('assert') or name in ('raises', 'warns', 'fail'):
                return True
    return False


def check_file(path):
    errors, warnings = [], []
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    except SyntaxError as e:
        return [f'{path}:{e.lineno}: no se puede analizar ({e.msg})'], []
    rel = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRS:
            errors.append(f'{rel}:{node.lineno}: prohibido `{node.attr}`: un test que falla debe quedar en rojo')
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in FORBIDDEN_ATTRS:
                    errors.append(f'{rel}:{node.lineno}: prohibido importar `{alias.name}`')
        elif isinstance(node, ast.Attribute) and node.attr in SKIP_ATTRS and rel != 'tests/integration/services/conftest.py':
            warnings.append(f'{rel}:{node.lineno}: `{node.attr}`: un test saltado no se ejecuta; ¿hay una razón de entorno documentada?')

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test'):
            if not has_assertion(node):
                warnings.append(f'{rel}:{node.lineno}: `{node.name}` no tiene ninguna aserción: no puede fallar')
    return errors, warnings


def main():
    targets = [Path(a).resolve() for a in sys.argv[1:]] or [ROOT / 'tests']
    files = []
    for target in targets:
        files.extend(sorted(target.rglob('*.py')) if target.is_dir() else [target])
    errors, warnings = [], []
    for path in files:
        if path.name == 'check_tests.py':
            continue
        e, w = check_file(path)
        errors += e
        warnings += w

    init = ROOT / 'tests' / '__init__.py'
    if init.exists() and init.read_text(encoding='utf-8').strip():
        warnings.append('tests/__init__.py no está vacío: debe estarlo para que los tests de backup no importen la app Flask')

    for line in warnings:
        print('AVISO ', line)
    for line in errors:
        print('ERROR ', line)
    print(f'\n{len(files)} archivos revisados: {len(errors)} errores, {len(warnings)} avisos')
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
