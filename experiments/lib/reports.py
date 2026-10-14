"""Normalize hidden-harness reports of different samples into one shape:
{passed, total, score, categories: {name: {passed, total}}, failed_ids: [...]}."""
import json


def normalize(d):
    if not isinstance(d, dict):
        return {'error': 'no report'}
    if 'totals' in d and 'checks_total' in (d.get('totals') or {}):      # S3-style (fixtures -> checks)
        t = d['totals']
        cats, failed = {}, []
        for f in d.get('fixtures', []):
            cats[f['name']] = {'passed': f.get('passed', 0), 'total': f.get('total', 0)}
            for c in f.get('checks', []):
                if not c.get('pass'):
                    failed.append(f"{f['name']}::{c.get('id')}")
        build = d.get('build')
        return {'passed': t['checks_passed'], 'total': t['checks_total'],
                'score': round(t['checks_passed'] / t['checks_total'], 4) if t['checks_total'] else 0,
                'categories': cats, 'failed_ids': failed, 'build': build}
    if 'passed' in d and 'total' in d:                                   # S1-style (flat checks)
        failed = [f"{c.get('category')}::{c.get('name')}" for c in d.get('checks', []) if not c.get('pass')]
        return {'passed': d['passed'], 'total': d['total'], 'score': d.get('score'),
                'categories': d.get('categories'), 'failed_ids': failed}
    return {'error': 'unknown report format', 'keys': list(d.keys())[:20]}


def load(path):
    try:
        with open(path, encoding='utf-8') as f:
            return normalize(json.load(f))
    except Exception as e:
        return {'error': f'no report: {e}'}
