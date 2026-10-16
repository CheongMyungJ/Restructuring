#!/usr/bin/env python3
"""Experiment 2: does the kit format keep the redevelopment free of the legacy STRUCTURE while keeping the behavior?

Runs on top of exp1.py (same workspaces, same redevelopment prompts and hidden harnesses):
  python3 exp1.py redev s4 V0 --reps 1,2                          # code only (port baseline)
  python3 exp1.py redev s4 V3,V4 --reps 1,2 --kit-method rekit_v2   # kit format 2 (module-organized, faithful pseudo-code)
  python3 exp1.py redev s4 V3,V4 --reps 1,2 --kit-method rekit_v3   # kit format 3 (neutral spec + clean-room design)
  python3 exp2_structure.py                                        # -> results/exp2_raw.{json,md}

Per redevelopment: hidden-test score + Legacy Structure Similarity (rekit.similarity: LSS, M1..M4).
Per kit: legacy-structure leaks in the parts an implementer reads as requirements (rekit.neutrality).
"""
import glob, json, os, statistics as st, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib'))
sys.path.insert(0, os.path.join(HERE, '..', 'plugins', 'rekit', 'engine'))
import reports  # noqa: E402
from rekit import similarity, neutrality  # noqa: E402

SP = os.environ.get('SP', '/tmp/claude-0/-home-user-Restructuring/9ce942c0-92ed-588d-ab07-51fb1b42752f/scratchpad')
EXP = os.path.join(SP, 'exp')
OUT = os.path.join(HERE, 'results')
LEGACY = {'s3': os.path.join(SP, 'samples', 's3_tlog', 'legacy'), 's4': os.path.join(SP, 'samples', 's4_ssdfw', 'legacy')}
# contract files: the redevelopment prompt requires them unchanged, so keeping them is not structural dependence
CONTRACTS = {'s3': [], 's4': ['fw_api.h', 'hal/*.h', 'hal_nand.h', 'hal_timer.h', 'hal_temp.h']}
KIT_LABEL = {'rekit_v2': 'F2 현행', 'rekit_v3': 'F3.0 신규(1차)', 'rekit_v3c': 'F3.1 신규(계약 경계 점검 추가)'}
KIT_LABEL.update({k + '@': v for k, v in KIT_LABEL.items()})


def kit_of(run_dir):
    v = run_dir.split(os.sep)[-2]
    return v.split('@')[1] if '@' in v else '-'


def redev_rows():
    rows = []
    for r in sorted(glob.glob(os.path.join(EXP, 'redev', '*', '*', '*', 'result.json'))):
        run = os.path.dirname(r)
        d = json.load(open(r))
        if d['sample'] not in LEGACY:
            continue
        kit = kit_of(run)
        if kit not in ('-', 'rekit_v2', 'rekit_v3', 'rekit_v3c'):
            continue
        sc = reports.load(os.path.join(run, 'score.json'))
        if sc.get('error'):
            sc = d.get('score') or {}
        sp = os.path.join(run, 'structure.json')
        new = os.path.join(run, 'ws', 'new')
        if os.path.isdir(new):
            sim = similarity.compare(LEGACY[d['sample']], new, CONTRACTS[d['sample']], detail=True)
            json.dump(sim, open(sp, 'w'), ensure_ascii=False, indent=1)
        sim = json.load(open(sp)) if os.path.exists(sp) else {}
        rows.append({'sample': d['sample'], 'variant': d['variant'], 'kit': kit, 'rep': d['rep'],
                     'score': sc.get('score'), 'passed': sc.get('passed'), 'total': sc.get('total'),
                     'LSS': sim.get('LSS'), 'M1': sim.get('M1_file_mirror'), 'M2': sim.get('M2_name_reuse'),
                     'M3': sim.get('M3_clone_ratio'), 'M4': sim.get('M4_function_mirror'),
                     'verbatim': sim.get('verbatim_ratio'), 'new_files': (sim.get('new') or {}).get('files'),
                     'new_loc': (sim.get('new') or {}).get('loc'),
                     'cost_usd': round(d['session'].get('cost_usd') or 0, 2),
                     'wall_min': round((d['session'].get('wall_s') or 0) / 60, 1), 'audit': d.get('audit_violations')})
    return rows


def kit_rows():
    rows = []
    for ws in sorted(glob.glob(os.path.join(EXP, 'gen', '*', 'rekit_v*'))):
        if not os.path.exists(os.path.join(ws, 'kit')):
            continue
        sample, method = ws.split(os.sep)[-2:]
        n = neutrality.scan(ws)['totals']
        state = json.load(open(os.path.join(ws, '.rekit', 'state.json')))
        sess = state.get('sessions', [])
        kb = 0
        for p in glob.glob(os.path.join(ws, 'kit', '**', '*'), recursive=True):
            if os.path.isfile(p) and p.endswith(('.md', '.json', '.txt')):
                kb += os.path.getsize(p)
        rows.append({'sample': sample, 'kit': method, 'done': all(v == 'done' for v in state.get('phases', {}).values()),
                     'cost_usd': round(sum(x.get('cost_usd') or 0 for x in sess), 2),
                     'wall_min': round(sum(x.get('wall_s') or 0 for x in sess) / 60, 1), 'sessions': len(sess),
                     'kit_kb': round(kb / 1024), **{f'leak_{k}': v for k, v in n.items()}})
    return rows


def fmt(x, pct=False):
    if x is None:
        return ''
    return f'{x:.0%}' if pct else str(x)


def main():
    os.makedirs(OUT, exist_ok=True)
    r, k = redev_rows(), kit_rows()
    json.dump({'kits': k, 'redevelopment': r}, open(os.path.join(OUT, 'exp2_raw.json'), 'w'), ensure_ascii=False, indent=1)
    L = ['# Experiment 2 raw results — structure independence', '',
         'F2 = kit format of the previous engine (module-organized spec, faithful pseudo-code, src refs inline);',
         'F3 = new format (legacy-neutral spec by capability + clean-room design + legacy_ref); F3.1 adds the contract boundary',
         'check (verbatim contract files). Workspace names: rekit_v2 / rekit_v3 / rekit_v3c.',
         '', '## Kits (generation cost, legacy-structure leaks in spec/design)', '',
         '| sample | kit | done | cost $ | wall min | sessions | kit KB | spec KB | internal-name hits | file-name hits | src refs | leaks/10KB |',
         '|---|---|---|---|---|---|---|---|---|---|---|---|']
    for x in k:
        L.append(f"| {x['sample']} | {KIT_LABEL.get(x['kit'], x['kit'])} | {x['done']} | {x['cost_usd']} | {x['wall_min']} | "
                 f"{x['sessions']} | {x['kit_kb']} | {round(x['leak_spec_bytes'] / 1024)} | {x['leak_symbols']} | "
                 f"{x['leak_file_names']} | {x['leak_src_refs']} | {x['leak_leaks_per_10kb']} |")
    L += ['', '## Redevelopment runs', '',
          '| sample | variant | kit | rep | hidden tests | LSS | M1 file | M2 names | M3 clone | M4 func | verbatim | new files/LOC | cost $ | min | audit |',
          '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for x in r:
        L.append(f"| {x['sample']} | {x['variant']} | {KIT_LABEL.get(x['kit'], x['kit'])} | {x['rep']} | {x['passed']}/{x['total']} | "
                 f"{fmt(x['LSS'])} | {fmt(x['M1'], 1)} | {fmt(x['M2'], 1)} | {fmt(x['M3'], 1)} | {fmt(x['M4'], 1)} | "
                 f"{fmt(x['verbatim'], 1)} | {x['new_files']}/{x['new_loc']} | {x['cost_usd']} | {x['wall_min']} | {x['audit']} |")
    agg = {}
    for x in r:
        if x['LSS'] is not None:
            agg.setdefault((x['sample'], x['variant'], x['kit']), []).append(x)
    L += ['', '## Mean by sample / variant / kit', '',
          '| sample | variant | kit | n | hidden tests (each) | mean LSS | M1 | M2 | M3 | M4 | mean cost $ | mean min |',
          '|---|---|---|---|---|---|---|---|---|---|---|---|']
    m = lambda xs, key: st.mean(x[key] for x in xs if x[key] is not None)
    for (s, v, kk), xs in sorted(agg.items()):
        L.append(f"| {s} | {v} | {KIT_LABEL.get(kk, kk)} | {len(xs)} | {', '.join(f'{x['passed']}/{x['total']}' for x in xs)} | "
                 f"{m(xs, 'LSS'):.1f} | {m(xs, 'M1'):.0%} | {m(xs, 'M2'):.0%} | {m(xs, 'M3'):.0%} | {m(xs, 'M4'):.0%} | "
                 f"{m(xs, 'cost_usd'):.2f} | {m(xs, 'wall_min'):.1f} |")
    open(os.path.join(OUT, 'exp2_raw.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
