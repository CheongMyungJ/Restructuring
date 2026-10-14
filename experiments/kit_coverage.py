#!/usr/bin/env python3
"""Deterministic coverage of a data package (kit/doc dir) against a legacy code inventory:
fraction of source files and of extracted symbols (functions/classes/SQL ids) mentioned anywhere in the package.
usage: kit_coverage.py <code_dir> <data_dir> [<data_dir> ...]"""
import glob, json, os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'plugins', 'rekit', 'engine'))
from rekit import inventory  # noqa: E402


def text_of(d):
    out = []
    for p in glob.glob(os.path.join(d, '**', '*'), recursive=True):
        if os.path.isfile(p) and p.endswith(('.md', '.json', '.txt', '.c', '.h', '.py', '.sh')):
            out.append(open(p, encoding='utf-8', errors='replace').read())
    return '\n'.join(out)


def main():
    code, dirs = sys.argv[1], sys.argv[2:]
    inv = inventory.scan([('code', code)])
    files = [f for f in inv['files'] if f['kind'] == 'text']
    syms = [(f['path'], s) for f in files for s in f.get('symbols', [])]
    res = {}
    for d in dirs:
        t = text_of(d)
        fref = sum(1 for f in files if os.path.basename(f['path']) in t)
        sref = sum(1 for _, s in syms if re.search(r'\b' + re.escape(s) + r'\b', t))
        res[d] = {'files': f'{fref}/{len(files)}', 'symbols': f'{sref}/{len(syms)}',
                  'symbol_cov': round(sref / max(1, len(syms)), 3), 'bytes': len(t.encode('utf-8')),
                  'tokens_est': int(len(t.encode('utf-8')) / 3.6)}
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
