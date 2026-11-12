"""Regenerate private/reports/tests/report.html from results.json + findings.json.

    python .claude/skills/test-bug-report/scripts/build_report.py

The HTML is a static template that renders the two JSON files: it tries to fetch them next to itself (live data when
served over http, e.g. `python -m http.server` inside the folder) and falls back to a copy embedded at build time, which
is what you get when you open the file by double-clicking (browsers block fetch() on file://).
"""
import json
import sys

from common import FINDINGS_FILE, REPORT_FILE, RESULTS_FILE, SKILL_DIR, load_json


def build():
    results = load_json(RESULTS_FILE)
    findings = load_json(FINDINGS_FILE, {'schema': 1, 'findings': []})
    if results is None:
        sys.exit('Falta %s: ejecuta antes run_tests.py' % RESULTS_FILE)
    template = (SKILL_DIR / 'assets' / 'report.template.html').read_text(encoding='utf-8')
    embedded = json.dumps({'results': results, 'findings': findings}, ensure_ascii=False).replace('</', '<\\/')
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(template.replace('__EMBEDDED_DATA__', embedded), encoding='utf-8')
    print('Reporte: %s' % REPORT_FILE)


if __name__ == '__main__':
    build()
