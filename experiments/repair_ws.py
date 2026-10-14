#!/usr/bin/env python3
"""Repair a rekit workspace after sessions failed (e.g. usage limit) but phases were marked done by an older engine.
Resets the earliest phase containing a failed session and everything after it; keeps completed units/reviews/fixes."""
import json, os, sys

PH = ['inventory', 'survey', 'units', 'synthesize', 'gate1', 'characterize', 'review', 'gate2', 'finalize']
STEP2PH = {'survey': 'survey', 'unit': 'units', 'synthesize': 'synthesize', 'synthesize_group': 'synthesize',
           'characterize': 'characterize', 'review': 'review', 'fix': 'review', 'finalize': 'finalize'}


def main(ws):
    sp = os.path.join(ws, '.rekit', 'state.json'); s = json.load(open(sp))
    bad = [x['step'] for x in s['sessions'] if x.get('error')]
    if not bad:
        print(ws, 'nothing to repair'); return
    phases = set()
    qp = os.path.join(ws, '.rekit', 'questions', 'store.json'); q = json.load(open(qp)) if os.path.exists(qp) else []
    for st in bad:
        kind, _, arg = st.partition(':')
        if kind == 'integrate':
            phases.add(arg)                                   # gate1 / gate2
            for x in q:
                if x.get('status') == 'answered' and not x['id'].startswith('Q-INTAKE'):
                    x['integrated'] = False
        elif kind == 'oracle':
            for x in q:
                if x.get('status') == 'deferred' and x.get('answer') == 'oracle gave no answer':
                    x['status'] = 'open'; x.pop('answer', None)
            phases.update(p for p in ('gate1', 'gate2') if s['phases'].get(p) in ('done', 'running') and p in ('gate2',)) or None
            phases.add('gate2' if s['phases'].get('review') == 'done' else 'gate1')
        else:
            phases.add(STEP2PH[kind])
            if kind == 'unit':
                s['units'][arg] = 'failed'
            if kind == 'review':
                g = os.path.join(ws, '.rekit', 'review', f'gaps_{arg}.json')
                if os.path.exists(g):
                    os.remove(g)
            if kind == 'synthesize_group':
                g = os.path.join(ws, '.rekit', 'groups', arg, 'summary.md')
                if os.path.exists(g):
                    os.remove(g)
    first = min(PH.index(p) for p in phases)
    for p in PH[first:]:
        s['phases'].pop(p, None)
    s['sessions'] = [x for x in s['sessions'] if not x.get('error')]
    json.dump(s, open(sp, 'w'), ensure_ascii=False, indent=1)
    if q:
        json.dump(q, open(qp, 'w'), ensure_ascii=False, indent=1)
    lr = os.path.join(ws, '.rekit', 'last_run.json')
    if os.path.exists(lr):
        os.remove(lr)
    print(ws.split('/exp/')[-1], 'failed:', sorted(set(bad))[:6], '... -> redo from', PH[first])


if __name__ == '__main__':
    for w in sys.argv[1:]:
        main(w)
