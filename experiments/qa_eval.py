#!/usr/bin/env python3
"""Experiment 2 scorer: can an implementer answer re-implementation questions from the kit alone?

1. answerer (fresh session, cwd = copy of the data only, read-only tools) answers every question with evidence;
   "UNKNOWN" when the data does not contain the answer.
2. grader (separate session) scores each answer against ground-truth key points.
Metrics: key-point recall, #correct/#partial/#unknown/#wrong (wrong = confidently incorrect = hallucination).
usage: qa_eval.py <data_dir> <qa.json> --out result.json [--answer-model sonnet] [--grade-model opus] [--tag name]
"""
import argparse, concurrent.futures as cf, json, os, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib'))
from claude_run import run_claude  # noqa: E402

ANSWER_PROMPT = """You are an engineer who must re-implement a legacy SSD firmware on a new platform. The ONLY information
you have is the documentation in the current directory (read it with Read/Glob/Grep). Answer the questions below
strictly from this documentation. Do NOT use outside/prior knowledge about any product. For each answer cite the
evidence (file path + short quote). If the documentation does not contain the answer, answer exactly "UNKNOWN".
Be precise (exact numbers, names, conditions).

Questions (JSON):
{questions}

Return the structured output: {{"answers": [{{"id": "...", "answer": "...", "evidence": "file: quote"}}]}}"""

GRADE_PROMPT = """You are grading answers to an exam about a legacy SSD firmware. For each item compare the candidate
answer with the ground truth and its key points. A key point counts as covered only if the candidate states it
correctly (numbers/conditions must match). Candidate answers "UNKNOWN" cover nothing (verdict "unknown").
Verdict: "correct" (all key points covered, nothing contradicting), "partial" (some covered, no major contradiction),
"wrong" (contradicts ground truth or states incorrect facts as true), "unknown" (UNKNOWN / no attempt).

Items (JSON):
{items}

Return the structured output: {{"grades": [{{"id": "...", "covered": <number of key points covered>, "total": <number of key points>, "verdict": "correct|partial|wrong|unknown", "note": "short reason"}}]}}"""

ANS_SCHEMA = {'type': 'object', 'properties': {'answers': {'type': 'array', 'items': {'type': 'object', 'properties': {
    'id': {'type': 'string'}, 'answer': {'type': 'string'}, 'evidence': {'type': 'string'}}, 'required': ['id', 'answer']}}},
    'required': ['answers']}
GRADE_SCHEMA = {'type': 'object', 'properties': {'grades': {'type': 'array', 'items': {'type': 'object', 'properties': {
    'id': {'type': 'string'}, 'covered': {'type': 'number'}, 'total': {'type': 'number'},
    'verdict': {'type': 'string', 'enum': ['correct', 'partial', 'wrong', 'unknown']}, 'note': {'type': 'string'}},
    'required': ['id', 'covered', 'total', 'verdict']}}}, 'required': ['grades']}


def last_result(log_path):
    try:
        for line in reversed(open(log_path, encoding='utf-8').read().splitlines()):
            if '"type":"result"' in line:
                return json.loads(line)
    except Exception:
        pass
    return {}


def chunks(xs, n):
    return [xs[i:i + n] for i in range(0, len(xs), n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('data_dir'); ap.add_argument('qa'); ap.add_argument('--out', required=True)
    ap.add_argument('--answer-model', default='sonnet'); ap.add_argument('--grade-model', default='opus')
    ap.add_argument('--batch', type=int, default=12); ap.add_argument('--parallel', type=int, default=3)
    a = ap.parse_args()
    qa = json.load(open(a.qa))
    work = tempfile.mkdtemp(prefix='qa_')
    box = os.path.join(work, 'data')
    shutil.copytree(a.data_dir, box, ignore=shutil.ignore_patterns('.git'))
    logs = os.path.splitext(a.out)[0] + '_logs'
    os.makedirs(logs, exist_ok=True)
    cost = 0.0

    def answer(i_batch):
        i, batch = i_batch
        qs = [{'id': q['id'], 'question': q['question']} for q in batch]
        r = run_claude(ANSWER_PROMPT.format(questions=json.dumps(qs, ensure_ascii=False, indent=1)), box,
                       os.path.join(logs, f'answer_{i}.jsonl'), model=a.answer_model, json_schema=ANS_SCHEMA,
                       extra_args=['--tools', 'Read,Glob,Grep'], timeout_s=3600)
        res = {}
        try:
            for x in (last_result(os.path.join(logs, f'answer_{i}.jsonl')).get('structured_output') or {}).get('answers', []):
                res[x['id']] = x
        except Exception:
            pass
        return res, r.get('cost_usd') or 0

    answers = {}
    with cf.ThreadPoolExecutor(a.parallel) as ex:
        for res, c in ex.map(answer, list(enumerate(chunks(qa, a.batch)))):
            answers.update(res); cost += c

    def grade(i_batch):
        i, batch = i_batch
        items = [{'id': q['id'], 'question': q['question'], 'ground_truth': q['answer'], 'key_points': q.get('key_points', []),
                  'candidate': (answers.get(q['id']) or {}).get('answer', 'UNKNOWN')} for q in batch]
        gdir = os.path.join(work, f'grade_{i}'); os.makedirs(gdir, exist_ok=True)
        r = run_claude(GRADE_PROMPT.format(items=json.dumps(items, ensure_ascii=False, indent=1)), gdir,
                       os.path.join(logs, f'grade_{i}.jsonl'), model=a.grade_model, json_schema=GRADE_SCHEMA,
                       extra_args=['--tools', ''], timeout_s=3600)
        res = {}
        try:
            for x in (last_result(os.path.join(logs, f'grade_{i}.jsonl')).get('structured_output') or {}).get('grades', []):
                res[x['id']] = x
        except Exception:
            pass
        return res, r.get('cost_usd') or 0

    grades = {}
    with cf.ThreadPoolExecutor(a.parallel) as ex:
        for res, c in ex.map(grade, list(enumerate(chunks(qa, a.batch)))):
            grades.update(res); cost += c

    rows, cov, tot, verdicts = [], 0, 0, {'correct': 0, 'partial': 0, 'wrong': 0, 'unknown': 0, 'ungraded': 0}
    for q in qa:
        g = grades.get(q['id'])
        kp = max(1, len(q.get('key_points') or []) or 1)
        if g:
            c = min(float(g.get('covered', 0)), kp)
            verdicts[g['verdict']] = verdicts.get(g['verdict'], 0) + 1
        else:
            c = 0; verdicts['ungraded'] += 1
        cov += c; tot += kp
        rows.append({'id': q['id'], 'category': q.get('category'), 'answer': (answers.get(q['id']) or {}).get('answer'),
                     'grade': g})
    by_cat = {}
    for q, r_ in zip(qa, rows):
        d = by_cat.setdefault(q.get('category', '?'), [0, 0])
        g = r_['grade'] or {}
        d[0] += min(float(g.get('covered', 0)), max(1, len(q.get('key_points') or []) or 1)); d[1] += max(1, len(q.get('key_points') or []) or 1)
    out = {'data_dir': a.data_dir, 'keypoint_recall': round(cov / tot, 4), 'verdicts': verdicts,
           'by_category': {k: round(v[0] / v[1], 3) for k, v in by_cat.items()}, 'eval_cost_usd': round(cost, 2), 'rows': rows}
    json.dump(out, open(a.out, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in ('keypoint_recall', 'verdicts', 'eval_cost_usd')}, ensure_ascii=False))
    shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    main()
