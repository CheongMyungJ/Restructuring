#!/usr/bin/env python3
"""Build trap variants of legacy_ref (temporary copies) and run the hidden harness on each.
usage: trap_variants.py [variant ...]      (prints score + failing checks per variant; see TRAPS.md)"""
import json, os, shutil, subprocess, sys, tempfile

HID = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(HID, 'legacy_ref')
HARN = os.path.join(HID, 'run_hidden_tests.py')
VD = tempfile.mkdtemp(prefix='s4_variants_')

PROD_DEF = [('config/fw_config.h', '#define CFG_NAND_TYPE   QLC', '#define CFG_NAND_TYPE   TLC'),
            ('config/fw_config.h', '#define CFG_OP_PERCENT  7', '#define CFG_OP_PERCENT  12')]

V = {
    'prod_defaults': PROD_DEF,
    'tlc_only': PROD_DEF[:1],
    'op12_only': PROD_DEF[1:],
    'c0_little_endian': PROD_DEF + [('host/nvme_vendor.c', 'put_be32((buf) + (off)', 'put_le32((buf) + (off)')],
    'smart_du_round_up': PROD_DEF + [('smart/smart.c', 'return raw512 / 1000;', 'return (raw512 + 999) / 1000;')],
    'smart_pct_cap100': PROD_DEF + [('smart/smart.c', 'if (pct > 255)\n        pct = 255;',
                                     'if (pct > 100)\n        pct = 100;')],
    'gc_tiebreak_oldest': PROD_DEF + [('ftl/ftl_gc.c',
                                       '(g_blk[b].valid == g_blk[best].valid && g_blk[b].ec < g_blk[best].ec))',
                                       '(g_blk[b].valid == g_blk[best].valid && g_blk[b].last_seq < g_blk[best].last_seq))')],
    'spare_threshold_5': PROD_DEF + [('config/fw_config.h', '#define SPARE_THRESHOLD_PCT     10',
                                      '#define SPARE_THRESHOLD_PCT     5')],
    'drop_c1': PROD_DEF + [('host/nvme_admin.c', '    case NVME_ADM_VS_SET_DEBUG:\n', '')],
}

names = sys.argv[1:] or list(V)
for n in names:
    d = os.path.join(VD, n)
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(REF, d)
    for f, a, b in V[n]:
        p = os.path.join(d, f)
        s = open(p).read()
        assert a in s, (n, f, a)
        open(p, 'w').write(s.replace(a, b, 1))
    rep = os.path.join(VD, n + '.json')
    subprocess.run(['python3', HARN, d, '--out', rep], capture_output=True, text=True)
    r = json.load(open(rep))
    fails = [(c['category'], c['name']) for c in r['checks'] if not c['pass']]
    print('%-20s %d/%d  fails=%s' % (n, r['overall']['pass'], r['overall']['total'], fails), flush=True)
shutil.rmtree(VD, ignore_errors=True)
