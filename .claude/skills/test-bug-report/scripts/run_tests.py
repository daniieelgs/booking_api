"""Run the whole suite (every tier) and store the outcome in private/reports/tests/results.json.

    python .claude/skills/test-bug-report/scripts/run_tests.py [--tiers unit integration services backup] [--no-report]

Use the project's virtualenv python (it needs pytest and the app dependencies). The integration tier takes ~1.5 min
and the services tier ~1.5 min more (it starts/stops the Docker test stack itself): run this in the background
and wait for it to finish. Tiers run one after another, never in parallel (shared SQLite file and containers).
"""
import argparse
import sys

from common import (FINDINGS_FILE, REPORT_DIR, RESULTS_FILE, TIER_ORDER, git_info, load_json, merge_tier, now_iso,
                    print_summary, run_tier, save_json, sync_findings)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--tiers', nargs='+', choices=TIER_ORDER, default=TIER_ORDER)
    parser.add_argument('--no-report', action='store_true', help='do not regenerate report.html')
    args = parser.parse_args()

    results = load_json(RESULTS_FILE, {'schema': 1, 'tiers': {}})
    results['schema'] = 1
    results['python'] = sys.version.split()[0]
    results['git'] = git_info()

    for tier in TIER_ORDER:
        if tier not in args.tiers:
            continue
        print('==> %s ...' % tier, flush=True)
        run = run_tier(tier)
        entry = merge_tier(results, tier, run)
        if entry['status'] == 'not_run':
            print('    NO MEDIDO: %s' % entry.get('reason'))
        else:
            counts = entry['counts']
            print('    %d tests, %d pasan, %d fallan (%.0f s)' % (counts['total'], counts['passed'], counts['failed'],
                                                                 entry.get('duration_seconds', 0)))
    results['generated_at'] = now_iso()
    save_json(RESULTS_FILE, results)

    findings = load_json(FINDINGS_FILE, {'schema': 1, 'findings': []})
    changes, unanalyzed = sync_findings(findings, results, 'run completo')
    if changes or not FINDINGS_FILE.exists():
        findings['updated_at'] = now_iso()
        save_json(FINDINGS_FILE, findings)

    print_summary(results)
    for finding_id, before, after in changes:
        print('  hallazgo %s: %s -> %s' % (finding_id, before, after))
    if unanalyzed:
        print('\nFALLOS SIN ANALIZAR (no están en findings.json), analízalos y añádelos:')
        for nodeid in unanalyzed:
            print('  -', nodeid)

    if not args.no_report:
        import build_report
        build_report.build()
    print('\nResultados: %s' % RESULTS_FILE)


if __name__ == '__main__':
    main()
