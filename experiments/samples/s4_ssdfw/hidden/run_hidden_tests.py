#!/usr/bin/env python3
"""Hidden black-box harness for S4 "ssdfw" (SSD controller firmware).

usage:
  run_hidden_tests.py <impl_dir> [--out report.json] [--keep] [-j N]
  run_hidden_tests.py --legacy-prod [--out report.json]   # candidate = legacy_ref, production flags
  run_hidden_tests.py --legacy-dev  [--out report.json]   # candidate = legacy_ref, repo defaults
  run_hidden_tests.py --gen-expected                      # regenerate expected/expected.json

Candidate contract:
  * `make -C <impl_dir> libssdfw.a` builds a static library WITHOUT any NAND/timer/temp HAL
    (the harness links its own simulator, harness/hsim.c, implementing hal/hal_nand.h).
  * headers `fw_api.h` and `hal/hal_nand.h` reachable via -I<impl_dir> (and -I<impl_dir>/include).
  * the candidate is built with NO extra -D flags.
Expected values come from hidden/legacy_ref built with the production flags
(-DCFG_NAND_TYPE=TLC -DCFG_OP_PERCENT=12, see provided_on_request/Makefile.release).
"""
import concurrent.futures as cf
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HARN = os.path.join(HERE, 'harness')
REF_SRC = os.path.join(HERE, 'legacy_ref')
EXP_FILE = os.path.join(HERE, 'expected', 'expected.json')
PROD_FLAGS = '-DCFG_NAND_TYPE=TLC -DCFG_OP_PERCENT=12'
CFLAGS = ['-std=gnu11', '-O2', '-w']
HSRC = ['hsim.c', 't_common.c', 't_ssd.c', 't_ssd2.c']
PL_CUTS = [0, 1, 3, 8, 21, 55, 144, 377, 610, 987, 1597, 2584, 4181, 6765]
SIMPLE = ['cmd', 'ident', 'integ', 'smart', 'vendor', 'features', 'gc_random', 'wl',
          'bb_factory', 'bb_progfail', 'bb_erasefail', 'bb_spare', 'rr', 'rd', 'pl_misc', 'thermal']
TIMEOUT = 600          # builds
RUN_TIMEOUT = 180      # per scenario process (legacy needs < 3 s)


def sh(cmd, cwd=None, timeout=TIMEOUT):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode(errors='replace') if isinstance(e.stdout, bytes) else (e.stdout or '')
        return 124, out, 'TIMEOUT'


# --------------------------------------------------------------------------- build
def build_lib(src, work, tag, flags=None, copy=True):
    """returns (include_flags, libpath, error)"""
    d = src
    if copy:
        d = os.path.join(work, tag + '_src')
        shutil.copytree(src, d)
        sh(['make', '-C', d, 'clean'])
    cmd = ['make', '-C', d, 'libssdfw.a']
    if flags:
        cmd.append('EXTRA_CFLAGS=' + flags)
    rc, out, err = sh(cmd)
    incs = ['-I' + d]
    if os.path.isdir(os.path.join(d, 'include')):
        incs.append('-I' + os.path.join(d, 'include'))
    libs = [os.path.join(d, 'libssdfw.a')] if os.path.exists(os.path.join(d, 'libssdfw.a')) else \
        sorted(glob.glob(os.path.join(d, '**', 'libssdfw.a'), recursive=True))
    if rc != 0 or not libs:
        return incs, None, 'make libssdfw.a failed (rc=%d)\n%s' % (rc, (out + err)[-3000:])
    return incs, libs[0], None


def build_test(incs, lib, work, tag):
    exe = os.path.join(work, 't_ssd_' + tag)
    srcs = [os.path.join(HARN, s) for s in HSRC]
    rc, out, err = sh(['cc', *CFLAGS, *incs, '-I' + HARN, *srcs, lib, '-lm', '-o', exe])
    if rc != 0:
        return None, (out + err)[-3000:]
    return exe, None


# --------------------------------------------------------------------------- run
def parse(stdout):
    res = {}
    for line in stdout.splitlines():
        if line.startswith('R '):
            parts = line.split(' ', 2)
            if len(parts) == 3:
                res[parts[1]] = parts[2].strip()
    return res


def run(exe, args):
    rc, out, err = sh([exe, *args], timeout=RUN_TIMEOUT)
    r = parse(out)
    if rc != 0:
        r['__error__%s' % '_'.join(args[:1])] = 'rc=%d %s' % (rc, err[-300:].replace('\n', ' '))
    return r


def run_all(cand, ref, work, jobs):
    """run every scenario; cand/ref are test executables. Returns merged result dict."""
    img = os.path.join(work, 'img')
    os.makedirs(img, exist_ok=True)
    P = lambda n: os.path.join(img, n)
    tasks = []
    for s in SIMPLE:
        tasks.append([(cand, [s])])
    for n in PL_CUTS:
        tasks.append([(cand, ['pl', '--n', str(n), '--tag', str(n)])])

    def chain(writer, reader, mode, tag, n='1500', extra_reader=None):
        w_mode = mode
        steps = [(writer, ['compat_w', '--mode', w_mode, '--n', n, '--out', P(tag + '.img'),
                           '--state', P(tag + '.st')])]
        r_mode = 'cut' if mode == 'cut' else 'clean'
        steps.append((reader, ['compat_r', '--mode', r_mode, '--in', P(tag + '.img'),
                               '--state', P(tag + '.st'), '--tag', tag] + (extra_reader or [])))
        return steps

    tasks.append(chain(ref, cand, 'clean', 'r2c_clean'))
    tasks.append(chain(ref, cand, 'cut', 'r2c_cut'))
    tasks.append(chain(ref, cand, 'pf', 'r2c_pf'))
    tasks.append(chain(cand, ref, 'clean', 'c2r_clean'))
    tasks.append(chain(cand, ref, 'cut', 'c2r_cut'))
    rt = chain(ref, cand, 'clean', 'rt1', extra_reader=['--out', P('rt2.img')])
    rt.append((ref, ['compat_r', '--mode', 'clean', '--in', P('rt2.img'), '--state',
                     P('rt2.img') + '.state', '--tag', 'rt2']))
    rt.append((cand, ['compat_r', '--mode', 'aged', '--n', '2400', '--in', P('rt1.img'),
                      '--state', P('rt1.st'), '--tag', 'aged80']))
    rt.append((cand, ['compat_r', '--mode', 'aged', '--n', '9000', '--in', P('rt1.img'),
                      '--state', P('rt1.st'), '--tag', 'aged255']))
    tasks.append(rt)

    def do_task(steps):
        r = {}
        for exe, args in steps:
            r.update(run(exe, args))
        return r

    merged = {}
    with cf.ThreadPoolExecutor(max_workers=jobs) as ex:
        for r in ex.map(do_task, tasks):
            merged.update(r)
    return merged


# --------------------------------------------------------------------------- checks
def C(cat, name, keys, cmp='eq', arg=None):
    return {'category': cat, 'name': name, 'keys': keys if isinstance(keys, list) else [keys],
            'cmp': cmp, 'arg': arg}


def checks():
    L = []
    a = L.append
    # command semantics & status codes
    a(C('cmd', 'invalid_opcodes', ['cmd_admin_bad_opc', 'cmd_io_bad_opc', 'cmd_write_zeroes', 'cmd_fw_download']))
    for k in ['cmd_read_oor', 'cmd_read_cross_end', 'cmd_read_last', 'cmd_write_oor']:
        a(C('cmd', k[4:], k))
    a(C('cmd', 'io_bad_nsid', ['cmd_io_nsid2', 'cmd_io_nsid0']))
    a(C('cmd', 'read_over_mdts', 'cmd_read_over_mdts'))
    a(C('cmd', 'mdts_read_write', 'cmd_mdts_rw'))
    a(C('cmd', 'flush_nsid', ['cmd_flush_bcast', 'cmd_flush_nsid2']))
    a(C('cmd', 'dsm_out_of_range', 'cmd_dsm_oor'))
    a(C('cmd', 'dsm_without_deallocate', 'cmd_dsm_no_ad'))
    a(C('cmd', 'log_invalid_lid', 'cmd_log_bad_lid'))
    a(C('cmd', 'log_smart_any_nsid', 'cmd_log_any_nsid'))
    a(C('cmd', 'log_partial_transfer', 'cmd_log_short'))
    a(C('cmd', 'identify_invalid', ['cmd_id_bad_cns', 'cmd_id_ns_bad_nsid']))
    a(C('cmd', 'identify_ns_list', 'cmd_id_nslist'))
    a(C('cmd', 'features_invalid', ['cmd_setf_bad_fid', 'cmd_setf_sv', 'cmd_getf_sel3', 'cmd_getf_bad_fid']))
    a(C('cmd', 'format_invalid', ['cmd_fmt_bad_lbaf', 'cmd_fmt_ses2', 'cmd_fmt_bad_nsid']))
    a(C('cmd', 'completion_cid_sqid', 'cmd_cid_echo'))
    a(C('cmd', 'error_log_count', 'cmd_errlog_delta'))
    a(C('cmd', 'host_cmd_counting', 'cmd_rw_cmds'))
    # identify
    for k in ['id_vid_ssvid', 'id_sn', 'id_mn', 'id_fr', 'id_oui_mdts', 'id_ver', 'id_oacs_npss',
              'id_wctemp_cctemp']:
        a(C('identify', k, k))
    a(C('identify', 'id_nn_oncs_vwc_qes', ['id_nn_oncs_vwc', 'id_sqes_cqes']))
    a(C('identify', 'ns_size_capacity', 'ns_nsze_ncap'))
    a(C('identify', 'ns_lba_format', ['ns_nlbaf_flbas_dlfeat', 'ns_lbaf0']))
    for k in ['ns_nuse_cached', 'ns_nuse_flushed', 'ns_nuse_trim']:
        a(C('identify', k, k))
    # data integrity
    for k in ['integ_cache_on', 'integ_cache_off', 'integ_fua_mix', 'integ_unwritten_zero', 'integ_fill',
              'integ_unaligned', 'integ_cache_overwrite', 'integ_refill_gc', 'integ_reboot_clean',
              'integ_reboot_abrupt', 'integ_format_ses0', 'integ_format_ses1', 'integ_format_reboot',
              'integ_gc_random', 'integ_gc_after_idle', 'integ_wl']:
        a(C('integrity', k, k))
    # SMART
    for k in ['smart_initial', 'smart_temp_initial', 'smart_du_floor', 'smart_cmds', 'smart_du_boundary',
              'smart_poh', 'smart_temp_stale', 'smart_temp_after_tick']:
        a(C('smart', k, k))
    a(C('smart', 'smart_cw_temp_threshold', ['smart_cw_tmpth_330', 'smart_cw_tmpth_eq', 'smart_cw_tmpth_334']))
    for k in ['smart_after_2_clean', 'smart_after_abrupt', 'smart_after_cut', 'smart_temp_reboot']:
        a(C('smart', k, k))
    a(C('smart', 'smart_aged_percentage_used', 'compat_aged80_smart'))
    a(C('smart', 'smart_aged_percentage_saturate', 'compat_aged255_smart'))
    # vendor
    for k in ['c0_sig_raw', 'c0_cdw0', 'c0_bad_raw', 'c0_raw_prefix', 'c0_free_ec', 'c0_dirty', 'c0_format_dirty']:
        a(C('vendor', k, k))
    a(C('vendor', 'c0_nand_programs', 'c0_nandprog', 'tol', 0.10))
    a(C('vendor', 'c1_debug_or_dropped', ['c1_set_debug', 'c1_bad_level'], 'alt', ['001/0|001']))
    # GC / WL
    a(C('gcwl', 'gc_count', 'gc_count', 'tol', 0.10))
    a(C('gcwl', 'gc_avg_ec', 'gc_avg_ec', 'tol', 0.10))
    a(C('gcwl', 'gc_ec_spread', 'gc_ec_spread', 'le_plus', 3))
    a(C('gcwl', 'gc_wl_random', 'gc_wl_random', 'abs', 3))
    a(C('gcwl', 'gc_nand_programs', 'gc_nandprog', 'tol', 0.10))
    a(C('gcwl', 'gc_idle', 'gc_idle', 'tuple_abs', [3, 2]))
    a(C('gcwl', 'gc_idle_thermal', 'gc_idle_thermal'))
    a(C('gcwl', 'wl_count', 'wl_count', 'tol_or_abs', [0.5, 10]))
    a(C('gcwl', 'wl_gc_count', 'wl_gc_count', 'tol', 0.10))
    a(C('gcwl', 'wl_ec_spread', 'wl_ec_spread', 'le_plus', 6))
    a(C('gcwl', 'wl_avg_ec', 'wl_avg_ec', 'tol', 0.15))
    # bad blocks
    for k in ['bb_factory_counts', 'bb_factory_fill', 'bb_pf_counts', 'bb_pf_spare', 'bb_pf_data', 'bb_pf_persist',
              'bb_pf_data_reboot', 'bb_ef_counts', 'bb_ef_spare', 'bb_ef_data', 'bb_spare9', 'bb_spare10',
              'bb_spare10_io']:
        a(C('badblock', k, k))
    # read retry
    for k in ['rr_l2', 'rr_l3', 'rr_l4', 'rr_l6', 'rr_l9', 'rr_l9_smart']:
        a(C('readretry', k, k))
    a(C('readretry', 'rr_recovered_no_media_error', ['rr_l2_smart', 'rr_l3_smart', 'rr_l4_smart', 'rr_l6_smart']))
    for k in ['rr_unc_rewrite', 'rr_totals', 'rr_data_all']:
        a(C('readretry', k, k))
    # read disturb
    for k in ['rd_at_limit', 'rd_over_limit', 'rd_data', 'rd_second']:
        a(C('readdisturb', k, k))
    # power loss
    for n in PL_CUTS:
        a(C('powerloss', 'pl_cut_%d' % n, 'pl_cut_%d' % n))
    for k in ['pl_cached_lost', 'pl_flush_survives', 'pl_fua_survives', 'pl_abrupt_shutdown',
              'pl_clean_shutdown', 'pl_double_cut', 'pl_format_cut']:
        a(C('powerloss', k, k))
    # on-NAND compatibility
    for t in ['r2c_clean', 'r2c_cut', 'r2c_pf', 'c2r_clean', 'c2r_cut', 'rt2']:
        a(C('compat', t + '_mount_data', ['compat_%s_mount' % t, 'compat_%s_data' % t]))
        a(C('compat', t + '_counters', ['compat_%s_counters' % t] +
            (['compat_%s_smart' % t] if 'cut' not in t else [])))
        a(C('compat', t + '_meta', ['compat_%s_bad' % t, 'compat_%s_sn_cap' % t]))
    a(C('compat', 'aged_mount', ['compat_aged80_mount', 'compat_aged255_mount']))
    # thermal
    a(C('thermal', 'th_poll_timing', ['th_no_sample', 'th_half_interval']))
    for k in ['th_l1', 'th_l2', 'th_l3', 'th_hold']:
        a(C('thermal', k, k))
    a(C('thermal', 'th_hysteresis', ['th_drop1', 'th_hyst_edge']))
    for k in ['th_drop_all', 'th_cache_limit', 'th_l3_writethrough', 'th_boot_level', 'th_l0_cached',
              'th_events_persist']:
        a(C('thermal', k, k))
    # features
    for k in ['feat_vwc_default', 'feat_vwc_off', 'feat_vwc_sel_default', 'feat_vwc_off_durable', 'feat_vwc_reset',
              'feat_tmpth_default', 'feat_tmpth_set', 'feat_ps_set', 'feat_ps_bad', 'feat_reset_reboot']:
        a(C('features', k, k))
    a(C('features', 'feat_tmpth_invalid', ['feat_tmpth_badsel', 'feat_tmpth_under']))
    # NAND protocol (implementation independent invariant)
    a(C('nand_protocol', 'no_protocol_violations', '__viol_sum__'))
    return L


def num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def compare(cmp, arg, exp, act):
    if act is None:
        return False, 'missing'
    if cmp == 'eq':
        return act == exp, ''
    if cmp == 'alt':
        return act == exp or act in arg, ''
    e, v = num(exp), num(act)
    if e is None or v is None:
        if cmp == 'tuple_abs':
            ep, vp = exp.split('/'), act.split('/')
            if len(ep) != len(vp):
                return False, 'shape'
            return all(num(x) is not None and num(y) is not None and abs(num(x) - num(y)) <= t
                       for x, y, t in zip(ep, vp, arg)), 'tol %s' % arg
        return False, 'not numeric'
    if cmp == 'tol':
        return abs(v - e) <= max(1.0, abs(e) * arg), 'rel tol %.0f%%' % (arg * 100)
    if cmp == 'abs':
        return abs(v - e) <= arg, 'abs tol %s' % arg
    if cmp == 'le_plus':
        return v <= e + arg, '<= expected+%s' % arg
    if cmp == 'tol_or_abs':
        return abs(v - e) <= max(abs(e) * arg[0], arg[1]), 'tol %s' % arg
    return False, 'unknown cmp'


def evaluate(res, exp, build_err):
    viol = [k for k in res if k.startswith('viol_')]
    res['__viol_sum__'] = str(sum(int(res[k]) for k in viol if res[k].isdigit())) if viol else None
    exp = dict(exp)
    exp['__viol_sum__'] = '0'
    out = [{'category': 'build', 'name': 'library_and_tests_build', 'pass': build_err is None,
            'expected': 'ok', 'actual': 'ok' if build_err is None else 'fail', 'detail': (build_err or '')[:1500]}]
    for c in checks():
        ev = '|'.join(str(exp.get(k)) for k in c['keys'])
        av = None if any(k not in res for k in c['keys']) else '|'.join(res[k] for k in c['keys'])
        if c['cmp'] in ('eq', 'alt'):
            ok, det = compare(c['cmp'], c['arg'], ev, av)
        else:                                   # numeric comparators use a single key
            ok, det = compare(c['cmp'], c['arg'], exp.get(c['keys'][0]), res.get(c['keys'][0]))
        out.append({'category': c['category'], 'name': c['name'], 'pass': bool(ok and av is not None),
                    'expected': ev, 'actual': av, 'detail': det})
    cats = {}
    for c in out:
        t = cats.setdefault(c['category'], {'pass': 0, 'total': 0})
        t['total'] += 1
        t['pass'] += 1 if c['pass'] else 0
    tot = sum(c['total'] for c in cats.values())
    ps = sum(c['pass'] for c in cats.values())
    errors = {k: v for k, v in res.items() if k.startswith('__error__')}
    return {'checks': out, 'categories': cats, 'errors': errors,
            'overall': {'pass': ps, 'total': tot, 'score': round(ps / tot, 4) if tot else 0.0}}


# --------------------------------------------------------------------------- main
def main():
    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        return 2
    out_path = args[args.index('--out') + 1] if '--out' in args else None
    jobs = int(args[args.index('-j') + 1]) if '-j' in args else max(1, min(4, os.cpu_count() or 1))
    keep = '--keep' in args
    gen = '--gen-expected' in args
    work = tempfile.mkdtemp(prefix='s4h_')
    try:
        ref_incs, ref_lib, err = build_lib(REF_SRC, work, 'ref', PROD_FLAGS)
        if err:
            print('reference build failed:\n' + err)
            return 3
        ref_exe, err = build_test(ref_incs, ref_lib, work, 'ref')
        if err:
            print('reference test build failed:\n' + err)
            return 3
        if gen or args[0] == '--legacy-prod':
            label = 'legacy_ref(prod flags)'
            cand_exe, build_err = ref_exe, None
        else:
            if args[0] == '--legacy-dev':
                label = 'legacy_ref(repo defaults)'
                incs, lib, build_err = build_lib(REF_SRC, work, 'cand', None)
            else:
                label = os.path.abspath(args[0])
                incs, lib, build_err = build_lib(label, work, 'cand', None, copy=False)
            cand_exe = None
            if not build_err:
                cand_exe, build_err = build_test(incs, lib, work, 'cand')
        res = run_all(cand_exe, ref_exe, work, jobs) if cand_exe else {}
        if gen:
            os.makedirs(os.path.dirname(EXP_FILE), exist_ok=True)
            clean = {k: v for k, v in sorted(res.items()) if not k.startswith('__')}
            with open(EXP_FILE, 'w') as f:
                json.dump(clean, f, indent=1, sort_keys=True)
            errs = [k for k in res if k.startswith('__error__')]
            print('expected written: %d keys -> %s%s' % (len(clean), EXP_FILE,
                                                        ('  ERRORS: %s' % errs) if errs else ''))
            return 0 if not errs else 1
        with open(EXP_FILE) as f:
            exp = json.load(f)
        rep = evaluate(res, exp, build_err)
        rep['implementation'] = label
        txt = json.dumps(rep, indent=1, ensure_ascii=False)
        if out_path:
            with open(out_path, 'w') as f:
                f.write(txt)
        for cat, t in sorted(rep['categories'].items()):
            print('%-14s %3d / %3d' % (cat, t['pass'], t['total']))
        o = rep['overall']
        print('OVERALL        %3d / %3d  (%.1f%%)' % (o['pass'], o['total'], 100.0 * o['score']))
        for c in rep['checks']:
            if not c['pass']:
                print('  FAIL %-12s %-34s exp=%s act=%s %s' % (c['category'], c['name'],
                                                            str(c['expected'])[:60], str(c['actual'])[:60],
                                                            c['detail']))
        return 0
    finally:
        if keep:
            print('work dir kept: ' + work)
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
