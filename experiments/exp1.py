#!/usr/bin/env python3
"""Experiment 1 driver: data format variants -> AI redevelopment fidelity.

Layout (EXP root, outside the repo):
  gen/<sample>/<method>/        generation workspace: input/{code,materials} -> kit/ or doc/
  redev/<sample>/<variant>/r<k>/ws/   redevelopment workspace (only the data for that variant) -> ws/new/
  redev/.../score.json          hidden test report
Variants:
  V0 code-only        legacy code + materials
  V1 naive-doc        doc/ from a one-shot "document this system" run
  V2 spec             kit/ without 07_tests/
  V3 spec+tests       kit/
  V4 spec+tests+code  kit/ + legacy code + materials
"""
import argparse, concurrent.futures as cf, json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib'))
from claude_run import run_claude  # noqa: E402

SP = os.environ.get('SP', '/tmp/claude-0/-home-user-Restructuring/9155ba45-e573-59a1-b70d-b72c0c21626d/scratchpad')
EXP = os.path.join(SP, 'exp')
SAMPLES = {
    's1': {'legacy': f'{SP}/samples/s1_nandftl/legacy', 'materials': f'{SP}/samples/s1_nandftl/materials',
           'harness': ['python3', f'{SP}/samples/s1_nandftl/hidden/run_hidden_tests.py'], 'redev_prompt': 'redev_s1.md'},
    's3': {'legacy': f'{SP}/samples/s3_tlog/legacy', 'materials': f'{SP}/samples/s3_tlog/materials',
           'harness': ['bash', f'{SP}/samples/s3_tlog/hidden/run_hidden_tests.sh'], 'redev_prompt': 'redev_s3.md'},
    's2': {'legacy': f'{SP}/samples/s2_cosmos/legacy', 'materials': f'{SP}/samples/s2_cosmos/materials'},
}
WATCH = [SP, '/home/user/Restructuring']
AVAILABLE = {
    'V0': 'Available information: the legacy source code in `./legacy/code/` and the documents handed over by the owners in `./legacy/materials/`.',
    'V1': 'Available information: the documentation of the legacy system in `./doc/`. The legacy source code is NOT available.',
    'V2': 'Available information: the redevelopment kit (specification of the legacy system) in `./kit/`. Start with `kit/README.md`. The legacy source code is NOT available.',
    'V3': 'Available information: the redevelopment kit (specification + tests of the legacy system) in `./kit/`. Start with `kit/README.md`. The legacy source code is NOT available.',
    'V4': 'Available information: the redevelopment kit in `./kit/` (start with `kit/README.md`), plus the legacy source code in `./legacy/code/` and the original documents in `./legacy/materials/`.',
}


def copytree(src, dst, ignore_tests=False):
    ign = shutil.ignore_patterns('.git', '*.o', '*.test', 'target') if not ignore_tests else shutil.ignore_patterns('.git', '07_tests')
    shutil.copytree(src, dst, ignore=ign, dirs_exist_ok=True)


def prep_gen(sample, method):
    ws = os.path.join(EXP, 'gen', sample, method)
    if os.path.exists(ws):
        shutil.rmtree(ws)
    copytree(SAMPLES[sample]['legacy'], os.path.join(ws, 'input', 'code'))
    copytree(SAMPLES[sample]['materials'], os.path.join(ws, 'input', 'materials'))
    return ws


def run_gen(sample, method, model='opus', prompt_file=None):
    ws = prep_gen(sample, method)
    prompt = open(os.path.join(HERE, 'prompts', prompt_file or (method + '.md')), encoding='utf-8').read()
    s = run_claude(prompt, ws, os.path.join(ws, 'session.jsonl'), model=model, timeout_s=4 * 3600,
                   watch_roots=WATCH, allowed_roots=[ws, os.path.expanduser('~/.m2'), '/tmp'])
    return s


def prep_redev(sample, variant, rep, kit_method='kitgen_v1', doc_method='naivedoc'):
    ws = os.path.join(EXP, 'redev', sample, variant, f'r{rep}', 'ws')
    if os.path.exists(os.path.dirname(ws)):
        shutil.rmtree(os.path.dirname(ws))
    os.makedirs(ws)
    gen_kit = os.path.join(EXP, 'gen', sample, kit_method, 'kit')
    gen_doc = os.path.join(EXP, 'gen', sample, doc_method, 'doc')
    if variant in ('V0', 'V4'):
        copytree(SAMPLES[sample]['legacy'], os.path.join(ws, 'legacy', 'code'))
        copytree(SAMPLES[sample]['materials'], os.path.join(ws, 'legacy', 'materials'))
    if variant == 'V1':
        copytree(gen_doc, os.path.join(ws, 'doc'))
    if variant == 'V2':
        copytree(gen_kit, os.path.join(ws, 'kit'), ignore_tests=True)
    if variant in ('V3', 'V4'):
        copytree(gen_kit, os.path.join(ws, 'kit'))
    return ws


def run_redev(sample, variant, rep, model='sonnet', kit_method='kitgen_v1', timeout_s=4 * 3600):
    ws = prep_redev(sample, variant, rep, kit_method=kit_method)
    tpl = open(os.path.join(HERE, 'prompts', SAMPLES[sample]['redev_prompt']), encoding='utf-8').read()
    prompt = tpl.replace('{{AVAILABLE}}', AVAILABLE[variant])
    s = run_claude(prompt, ws, os.path.join(os.path.dirname(ws), 'session.jsonl'), model=model, timeout_s=timeout_s,
                   watch_roots=WATCH, allowed_roots=[ws, os.path.expanduser('~/.m2'), '/tmp'])
    sc = score(sample, ws)
    out = {'sample': sample, 'variant': variant, 'rep': rep, 'model': model, 'kit_method': kit_method,
           'session': {k: s.get(k) for k in ('cost_usd', 'wall_s', 'num_turns', 'is_error', 'timed_out')},
           'audit_violations': s['audit'].get('violation_count'), 'score': sc}
    json.dump(out, open(os.path.join(os.path.dirname(ws), 'result.json'), 'w'), ensure_ascii=False, indent=1)
    return out


def score(sample, ws):
    rep = os.path.join(os.path.dirname(ws), 'score.json')
    cmd = SAMPLES[sample]['harness'] + [os.path.join(ws, 'new'), '--out', rep]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=3 * 3600)
        open(os.path.join(os.path.dirname(ws), 'score.log'), 'w').write(p.stdout[-20000:] + '\n' + p.stderr[-20000:])
    except subprocess.TimeoutExpired:
        return {'error': 'harness timeout'}
    try:
        r = json.load(open(rep))
        return {k: r.get(k) for k in ('passed', 'total', 'score', 'categories')}
    except Exception as e:
        return {'error': 'no report: %s' % e}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd')
    g = sub.add_parser('gen'); g.add_argument('sample'); g.add_argument('method'); g.add_argument('--model', default='opus'); g.add_argument('--prompt')
    r = sub.add_parser('redev'); r.add_argument('sample'); r.add_argument('variants'); r.add_argument('--reps', default='1')
    r.add_argument('--model', default='sonnet'); r.add_argument('--kit-method', default='kitgen_v1'); r.add_argument('--parallel', type=int, default=3)
    s = sub.add_parser('score'); s.add_argument('sample'); s.add_argument('ws')
    a = ap.parse_args()
    if a.cmd == 'gen':
        res = run_gen(a.sample, a.method, a.model, a.prompt)
        print(json.dumps({k: res.get(k) for k in ('cost_usd', 'wall_s', 'num_turns', 'is_error', 'timed_out')}), 'audit', res['audit'].get('violation_count'))
    elif a.cmd == 'redev':
        jobs = [(a.sample, v, int(k)) for v in a.variants.split(',') for k in a.reps.split(',')]
        with cf.ThreadPoolExecutor(a.parallel) as ex:
            futs = {ex.submit(run_redev, s_, v, k, a.model, a.kit_method): (s_, v, k) for s_, v, k in jobs}
            for f in cf.as_completed(futs):
                try:
                    o = f.result()
                    print(json.dumps({'job': futs[f], 'score': o['score'].get('score'), 'passed': o['score'].get('passed'),
                                      'total': o['score'].get('total'), 'cost': o['session']['cost_usd'],
                                      'wall_s': o['session']['wall_s'], 'audit': o['audit_violations']}), flush=True)
                except Exception as e:
                    print(json.dumps({'job': futs[f], 'error': repr(e)}), flush=True)
    elif a.cmd == 'score':
        print(json.dumps(score(a.sample, a.ws)))


if __name__ == '__main__':
    main()
