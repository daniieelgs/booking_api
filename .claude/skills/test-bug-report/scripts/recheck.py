"""Re-run only the tests behind some findings (not the whole suite) and update results.json + findings.json.

    python .claude/skills/test-bug-report/scripts/recheck.py --finding F-003 F-004
    python .claude/skills/test-bug-report/scripts/recheck.py --open              # every finding still open
    python .claude/skills/test-bug-report/scripts/recheck.py --tests "tests/unit/test_x.py::TestY::test_z"

A finding whose tests all pass becomes `fixed`; one that fails again (or was fixed before) becomes/stays `open` with
its latest failure attached. Findings without tests (kind "extra") are never touched here: use findings.py status.
"""
import argparse
import sys

from common import (FINDINGS_FILE, RESULTS_FILE, TIER_ORDER, load_json, merge_tier, now_iso, print_summary, run_tier,
                    save_json, sync_findings, tier_of)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--finding', nargs='+', metavar='ID')
    group.add_argument('--open', action='store_true', help='re-run the tests of every open finding')
    group.add_argument('--tests', nargs='+', metavar='NODEID')
    parser.add_argument('--no-report', action='store_true')
    args = parser.parse_args()

    results = load_json(RESULTS_FILE)
    findings = load_json(FINDINGS_FILE)
    if results is None or findings is None:
        sys.exit('Falta results.json o findings.json: ejecuta primero run_tests.py y el análisis.')

    if args.tests:
        nodeids = args.tests
    else:
        wanted = None if args.open else set(args.finding)
        nodeids = []
        for finding in findings['findings']:
            if wanted is not None and finding['id'] not in wanted:
                continue
            if wanted is None and finding.get('status') != 'open':
                continue
            nodeids.extend(t for t in finding.get('tests', []) if t not in nodeids)
        if wanted:
            missing = wanted - {f['id'] for f in findings['findings']}
            if missing:
                sys.exit('Hallazgos inexistentes: %s' % ', '.join(sorted(missing)))
    if not nodeids:
        sys.exit('Nada que re-ejecutar: los hallazgos indicados no tienen tests asociados.')

    by_tier = {}
    for nodeid in nodeids:
        tier = tier_of(nodeid)
        if tier is None:
            sys.exit('No sé a qué nivel pertenece %s (debe empezar por tests/unit, tests/integration, tests/backup...)' % nodeid)
        by_tier.setdefault(tier, []).append(nodeid)

    not_found = []
    for tier in TIER_ORDER:
        if tier not in by_tier:
            continue
        print('==> %s: %d test(s)' % (tier, len(by_tier[tier])), flush=True)
        run = run_tier(tier, by_tier[tier])
        if run['note'] and not run['tests']:
            print('    NO MEDIDO: %s' % run['note'])
            continue
        merge_tier(results, tier, run, partial=True)
        not_found.extend(n for n in by_tier[tier] if n not in run['tests'])

    results['generated_at'] = now_iso()
    save_json(RESULTS_FILE, results)
    changes, _ = sync_findings(findings, results, 're-verificación')
    findings['updated_at'] = now_iso()
    save_json(FINDINGS_FILE, findings)

    print_summary(results)
    for finding_id, before, after in changes:
        print('  hallazgo %s: %s -> %s' % (finding_id, before, after))
    if not changes:
        print('  (ningún hallazgo ha cambiado de estado)')
    if not_found:
        print('\nTests que pytest no encontró (¿renombrados o borrados? actualiza el hallazgo):')
        for nodeid in not_found:
            print('  -', nodeid)

    if not args.no_report:
        import build_report
        build_report.build()


if __name__ == '__main__':
    main()
