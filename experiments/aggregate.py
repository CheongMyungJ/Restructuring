#!/usr/bin/env python3
"""Aggregate experiment results into JSON + Markdown tables (experiments/results/)."""
import glob, json, os, statistics as st, sys

SP = os.environ.get('SP', '/tmp/claude-0/-home-user-Restructuring/9155ba45-e573-59a1-b70d-b72c0c21626d/scratchpad')
EXP = os.path.join(SP, 'exp')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')


def gen_costs():
    rows = {}
    for s in glob.glob(os.path.join(EXP, 'gen', '*', '*', 'session.jsonl.summary.json')):
        d = json.load(open(s)); parts = s.split(os.sep)
        rows[f'{parts[-3]}/{parts[-2]}'] = {'cost_usd': round(d.get('cost_usd') or 0, 2), 'wall_min': round((d.get('wall_s') or 0) / 60, 1)}
    for st_ in glob.glob(os.path.join(EXP, 'gen', '*', '*', '.rekit', 'state.json')):
        d = json.load(open(st_)); parts = st_.split(os.sep)
        sess = d.get('sessions', [])
        rows[f'{parts[-4]}/{parts[-3]}'] = {'cost_usd': round(sum(x.get('cost_usd') or 0 for x in sess), 2),
                                            'wall_min': round(sum(x.get('wall_s') or 0 for x in sess) / 60, 1),
                                            'sessions': len(sess), 'phases': d.get('phases')}
    return rows


def redev_results():
    rows = []
    for r in sorted(glob.glob(os.path.join(EXP, 'redev', '*', '*', '*', 'result.json'))):
        d = json.load(open(r))
        sc = d.get('score') or {}
        rows.append({'sample': d['sample'], 'variant': d['variant'], 'rep': d['rep'], 'kit_method': d.get('kit_method'),
                     'score': sc.get('score'), 'passed': sc.get('passed'), 'total': sc.get('total'),
                     'categories': sc.get('categories'), 'cost_usd': round(d['session'].get('cost_usd') or 0, 2),
                     'wall_min': round((d['session'].get('wall_s') or 0) / 60, 1), 'audit': d.get('audit_violations'),
                     'dir': os.path.dirname(r)})
    return rows


def main():
    os.makedirs(OUT, exist_ok=True)
    g, r = gen_costs(), redev_results()
    json.dump({'generation': g, 'redevelopment': r}, open(os.path.join(OUT, 'exp_raw.json'), 'w'), ensure_ascii=False, indent=1)
    lines = ['# Raw experiment results', '', '## Generation', '', '| sample/method | cost $ | wall min | sessions |', '|---|---|---|---|']
    for k, v in sorted(g.items()):
        lines.append(f"| {k} | {v['cost_usd']} | {v['wall_min']} | {v.get('sessions', 1)} |")
    lines += ['', '## Redevelopment (hidden tests)', '', '| sample | variant | kit | rep | score | passed/total | cost $ | wall min | audit |', '|---|---|---|---|---|---|---|---|---|']
    for x in r:
        lines.append(f"| {x['sample']} | {x['variant']} | {x['kit_method']} | {x['rep']} | {x['score']} | {x['passed']}/{x['total']} | {x['cost_usd']} | {x['wall_min']} | {x['audit']} |")
    agg = {}
    for x in r:
        if x['score'] is None:
            continue
        agg.setdefault((x['sample'], x['variant'], x['kit_method']), []).append(x)
    lines += ['', '## Mean by variant', '', '| sample | variant | kit | n | mean score | mean cost $ | mean wall min |', '|---|---|---|---|---|---|---|']
    for (s, v, k), xs in sorted(agg.items()):
        lines.append(f"| {s} | {v} | {k} | {len(xs)} | {st.mean(x['score'] for x in xs):.3f} | {st.mean(x['cost_usd'] for x in xs):.2f} | {st.mean(x['wall_min'] for x in xs):.1f} |")
    open(os.path.join(OUT, 'exp_raw.md'), 'w').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
