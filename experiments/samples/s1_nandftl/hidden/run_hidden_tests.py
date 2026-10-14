#!/usr/bin/env python3
"""Hidden black-box harness for S1 (NFL NAND flash layer).
usage: run_hidden_tests.py <impl_dir> [--out report.json] [--gen-expected]
Contract for implementations: headers reachable as "nfl/map.h", "nfl/nand.h", "nfl/error.h" from <impl_dir> (or <impl_dir>/include);
either `make -C <impl_dir> libnfl.a` builds a static library, or sources live in <impl_dir>/nfl/*.c (or <impl_dir>/src/**/*.c)."""
import json, os, re, shutil, subprocess, sys, tempfile, glob

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'src')
REF = os.path.join(HERE, 'legacy_ref')
EXP = os.path.join(HERE, 'expected', 'golden.txt')
CFLAGS = ['-std=gnu11', '-O1', '-w']

def sh(cmd, cwd=None, timeout=300):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout or b'').decode() if isinstance(e.stdout, bytes) else (e.stdout or ''), 'TIMEOUT'

def build_lib(impl, work, tag):
    incs = ['-I' + impl]
    if os.path.isdir(os.path.join(impl, 'include')):
        incs.append('-I' + os.path.join(impl, 'include'))
    if os.path.exists(os.path.join(impl, 'Makefile')):
        rc, out, err = sh(['make', '-C', impl, 'libnfl.a'], timeout=600)
        cand = glob.glob(os.path.join(impl, '**', 'libnfl.a'), recursive=True)
        if rc == 0 and cand:
            return incs, [cand[0]], None
    srcs = sorted(glob.glob(os.path.join(impl, 'nfl', '*.c')))
    if not srcs:
        srcs = sorted(p for p in glob.glob(os.path.join(impl, 'src', '**', '*.c'), recursive=True)
                      if not re.search(r'(test|sim|main)', os.path.basename(p)))
    if not srcs:
        return incs, [], 'no library sources found'
    objs = []
    for s in srcs:
        o = os.path.join(work, tag + '_' + os.path.basename(s) + '.o')
        rc, out, err = sh(['cc', *CFLAGS, *incs, '-c', s, '-o', o])
        if rc != 0:
            return incs, [], 'compile failed: %s\n%s' % (s, err[-2000:])
        objs.append(o)
    return incs, objs, None

def build_test(name, incs, libs, work, tag):
    exe = os.path.join(work, '%s_%s' % (name, tag))
    rc, out, err = sh(['cc', *CFLAGS, *incs, '-I' + SRC, os.path.join(SRC, name + '.c'), os.path.join(SRC, 'sim2.c'), *libs, '-o', exe])
    if rc != 0:
        return None, err[-3000:]
    return exe, None

def golden_lines(text):
    return [l for l in text.splitlines() if l.startswith(('HARD ', 'SOFT '))]

def main():
    args = sys.argv[1:]
    impl = os.path.abspath(args[0])
    out_path = args[args.index('--out') + 1] if '--out' in args else None
    gen = '--gen-expected' in args
    work = tempfile.mkdtemp(prefix='s1h_')
    checks = []
    def add(cat, name, ok, detail=''):
        checks.append({'category': cat, 'name': name, 'pass': bool(ok), 'detail': detail[:400]})

    ref_incs, ref_libs, err = build_lib(REF, work, 'ref')
    assert not err, err
    incs, libs, err = build_lib(impl, work, 'cand')
    build_ok = err is None
    add('build', 'library_builds', build_ok, err or '')
    exes = {}
    for t in ('t_api', 't_golden', 't_compat'):
        exes[('ref', t)], e = build_test(t, ref_incs, ref_libs, work, 'ref')
        assert exes[('ref', t)], e
        if build_ok:
            exes[('cand', t)], e = build_test(t, incs, libs, work, 'cand')
            add('build', 'test_%s_links' % t, exes[('cand', t)] is not None, e or '')
        else:
            exes[('cand', t)] = None

    if gen:
        rc, out, _ = sh([exes[('ref', 't_golden')]], timeout=600)
        os.makedirs(os.path.dirname(EXP), exist_ok=True)
        open(EXP, 'w').write('\n'.join(golden_lines(out)) + '\n')
        print('expected written:', len(golden_lines(out)), 'lines')

    # 1) API functional checks
    names = ['api_basic_multi_seed', 'api_other_geometry', 'api_synced_survive_power_loss', 'api_resume_blank_chip', 'api_error_semantics']
    if exes[('cand', 't_api')]:
        rc, out, errt = sh([exes[('cand', 't_api')]], timeout=600)
        got = {m.group(1): (m.group(2) == 'PASS', m.group(3)) for m in re.finditer(r'^CHECK (\S+) (PASS|FAIL) ?(.*)$', out, re.M)}
        for n in names:
            ok, d = got.get(n, (False, 'missing (crash/timeout rc=%d) %s' % (rc, errt[-200:])))
            add('api', n, ok, d)
    else:
        for n in names: add('api', n, False, 'not built')

    # 2) golden trace
    exp = [l for l in open(EXP).read().splitlines() if l]
    got_lines = []
    if exes[('cand', 't_golden')]:
        rc, out, errt = sh([exes[('cand', 't_golden')]], timeout=900)
        got_lines = golden_lines(out)
    def key(l):
        m = re.match(r'(HARD|SOFT) (\S+) ?(.*?)(->|resume=|written=|r=|ok=|size=|prog=|spread=|$)', l)
        if l.startswith('HARD CAP'): return l.split(' -> ')[0]
        if l.startswith('HARD PL'): return ' '.join(l.split()[:4])
        if l.startswith('HARD FILL'): return ' '.join(l.split()[:3])
        return ' '.join(l.split()[:2])
    gmap = {}
    for l in got_lines: gmap.setdefault(key(l), l)
    for l in exp:
        k = key(l)
        g = gmap.get(k)
        if l.startswith('HARD'):
            cat = {'CAP': 'capacity', 'FILL': 'fill', 'FILL_REWRITE': 'fill', 'FILL_VERIFY': 'fill', 'PL': 'power_loss', 'WORKLOAD': 'workload'}.get(l.split()[1], 'golden')
            add(cat, k, g == l, '' if g == l else 'expected: %s | got: %s' % (l[-120:], (g or 'MISSING')[-120:]))
        else:
            ev = dict(re.findall(r'(\w+)=(\d+)', l)); gv = dict(re.findall(r'(\w+)=(\d+)', g or ''))
            if l.startswith('SOFT OPS'):
                for f in ('prog', 'erase'):
                    e_, g_ = int(ev[f]), int(gv.get(f, -10**9))
                    add('perf', 'ops_' + f + '_within_10pct', abs(g_ - e_) <= 0.10 * e_, 'expected %d got %d' % (e_, g_))
            elif l.startswith('SOFT WEAR'):
                e_, g_ = int(ev['spread']), int(gv.get('spread', 10**9))
                add('perf', 'wear_spread_le_legacy_plus1', g_ <= e_ + 1, 'legacy %d got %d' % (e_, g_))

    # 3) on-flash compatibility (both directions)
    for seed in (1, 2):
        for a, b in (('ref', 'cand'), ('cand', 'ref')):
            name = 'compat_seed%d_%s_writes_%s_reads' % (seed, a, b)
            if not exes[('cand', 't_compat')]:
                add('compat', name, False, 'not built'); continue
            img1 = os.path.join(work, 'img1_%d_%s' % (seed, a)); img2 = os.path.join(work, 'img2_%d_%s' % (seed, a))
            r1 = sh([exes[(a, 't_compat')], 'write', str(seed), img1], timeout=300)
            r2 = sh([exes[(b, 't_compat')], 'verify', str(seed), img1, '1'], timeout=300)
            add('compat', name, r1[0] == 0 and r2[0] == 0, (r1[1] + r2[1] + r2[2][-200:]).strip())
            r3 = sh([exes[(b, 't_compat')], 'append', str(seed), img1, img2], timeout=300)
            r4 = sh([exes[(a, 't_compat')], 'verify', str(seed), img2, '2'], timeout=300)
            add('compat', name + '_then_append_roundtrip', r1[0] == 0 and r3[0] == 0 and r4[0] == 0, (r3[1] + r4[1] + r4[2][-200:]).strip())

    cats = {}
    for c in checks:
        d = cats.setdefault(c['category'], [0, 0]); d[1] += 1; d[0] += c['pass']
    total = sum(v[1] for k, v in cats.items() if k != 'build'); passed = sum(v[0] for k, v in cats.items() if k != 'build')
    report = {'impl': impl, 'passed': passed, 'total': total, 'score': round(passed / total, 4) if total else 0,
              'categories': {k: {'passed': v[0], 'total': v[1]} for k, v in cats.items()}, 'checks': checks}
    s = json.dumps(report, ensure_ascii=False, indent=1)
    if out_path: open(out_path, 'w').write(s)
    print(json.dumps({k: report[k] for k in ('passed', 'total', 'score', 'categories')}, ensure_ascii=False))
    shutil.rmtree(work, ignore_errors=True)

if __name__ == '__main__':
    main()
