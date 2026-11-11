"""Read and edit findings.json without opening the HTML or running any test.

    findings.py list [--status open|fixed|wontfix] [--tier unit|integration|services|backup] [--size small|medium|discuss]
    findings.py show F-003            # the whole finding as JSON: tests, root cause, evidence, files, suggested fix
    findings.py status F-011 wontfix --note "decidido con el equipo"
    findings.py add path/to/finding.json   # append (or replace by id) a finding written by hand
"""
import argparse
import json
import sys

from common import FINDINGS_FILE, load_json, now_iso, save_json


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
    args = parser.parse_args()

    data = load() if args.cmd != 'add' else (load_json(FINDINGS_FILE) or {'schema': 1, 'findings': []})
    items = data['findings']

    if args.cmd == 'list':
        for f in items:
            if args.status and f.get('status') != args.status:
                continue
            if args.tier and f.get('tier') != args.tier:
                continue
            if args.size and f.get('change_size') != args.size:
                continue
            print('%-6s %-7s %-12s %-8s %-8s %s' % (f['id'], f.get('status'), f.get('tier') or 'extra', f.get('severity'),
                                                    f.get('change_size'), f['title']))
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
