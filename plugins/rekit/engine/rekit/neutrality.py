"""Deterministic scan for legacy-structure leaks in the legacy-neutral layers of a kit (spec + design).

A leak is a legacy INTERNAL name (function/type/class/macro/variable symbol of the inventory), a legacy source file
name, or an inline source reference, written into a file the implementer reads as requirements. Names (and file names) that
appear in the contract files (03_interfaces, 04_data) are contract identifiers and are allowed.
"""
import glob, os, re

from .util import read_json

SPEC_GLOBS = ['*.md', '05_behavior/**/*.md', '07_tests/README.md', '07_tests/vectors/**/*.md', 'design/**/*.md']
CONTRACT_GLOBS = ['03_interfaces/**/*', '04_data/**/*']
NOT_SCANNED = {'09_open_questions.md'}        # generated from questions (their context cites code on purpose)
# names every codebase of the language/build tool has: not legacy-specific structure
GENERIC = {'toString', 'hashCode', 'equals', 'main', 'README.md', 'pom.xml', 'build.gradle', 'settings.gradle',
           'Makefile', 'CMakeLists.txt', 'logback.xml', 'log4j2.xml', 'application.yml', 'application.properties',
           'package.json', 'build.sh', '.gitignore'}
SRC_RE = re.compile(r'\(src:[^)]*\)|\bsrc:\s*\S+:\d+')


def code_like(sym):
    """Only names that cannot be ordinary prose words: snake_case, camelCase, ALL_CAPS_WITH_UNDERSCORE, >= 4 chars."""
    if len(sym) < 4:
        return False
    return '_' in sym.strip('_') or re.search(r'[a-z][A-Z]', sym) is not None or re.match(r'^[A-Z][a-z]+[A-Z]', sym)


def _files(kit, globs):
    out = set()
    for g in globs:
        out |= {p for p in glob.glob(os.path.join(kit, g), recursive=True) if os.path.isfile(p)}
    return sorted(out)


def _text(p):
    with open(p, encoding='utf-8', errors='replace') as f:
        return f.read()


def scan(ws):
    kit = os.path.join(ws, 'kit')
    inv = read_json(os.path.join(ws, '.rekit', 'inventory.json'), {}) or {}
    contract_text = '\n'.join(_text(p) for p in _files(kit, CONTRACT_GLOBS))
    contract_ids = set(re.findall(r'[A-Za-z_][A-Za-z0-9_]*', contract_text))
    syms, fnames = set(), set()
    for f in inv.get('files', []):
        if f.get('kind') != 'text':
            continue
        syms |= {s for s in f.get('symbols', []) if code_like(s)}
        base = os.path.basename(f['path'])
        if '.' in base and len(base) >= 5:
            fnames.add(base)
    internal = syms - contract_ids - GENERIC
    sym_re = re.compile(r'(?<![A-Za-z0-9_])(' + '|'.join(sorted(map(re.escape, internal), key=len, reverse=True)) +
                        r')(?![A-Za-z0-9_])') if internal else None
    fnames = {f for f in fnames if f not in contract_text and f not in GENERIC}     # e.g. a run script named by the ops contract
    fn_re = re.compile(r'(?<![\w./-])(' + '|'.join(sorted(map(re.escape, fnames), key=len, reverse=True)) +
                       r')(?![\w])') if fnames else None
    report = {'files': {}, 'totals': {'symbols': 0, 'file_names': 0, 'src_refs': 0, 'spec_files': 0,
                                      'spec_bytes': 0},
              'internal_symbols_known': len(internal)}
    for p in _files(kit, SPEC_GLOBS):
        rel = os.path.relpath(p, kit)
        if rel in NOT_SCANNED or rel.startswith(('legacy_ref', '03_interfaces', '04_data')):
            continue
        t = _text(p)
        report['totals']['spec_files'] += 1
        report['totals']['spec_bytes'] += len(t.encode('utf-8'))
        hits = {}
        for m in (sym_re.finditer(t) if sym_re else ()):
            hits[m.group(1)] = hits.get(m.group(1), 0) + 1
        fhits = {}
        for m in (fn_re.finditer(t) if fn_re else ()):
            fhits[m.group(1)] = fhits.get(m.group(1), 0) + 1
        srcs = len(SRC_RE.findall(t))
        if hits or fhits or srcs:
            report['files'][rel] = {'symbols': hits, 'file_names': fhits, 'src_refs': srcs}
        report['totals']['symbols'] += sum(hits.values())
        report['totals']['file_names'] += sum(fhits.values())
        report['totals']['src_refs'] += srcs
    tot = report['totals']
    tot['leaks'] = tot['symbols'] + tot['file_names'] + tot['src_refs']
    tot['leaks_per_10kb'] = round(10240 * tot['leaks'] / tot['spec_bytes'], 2) if tot['spec_bytes'] else 0.0
    tot['distinct_symbols'] = len({s for v in report['files'].values() for s in v['symbols']})
    return report
