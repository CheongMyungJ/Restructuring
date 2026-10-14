"""rekit pipeline: inventory → survey → unit analysis (parallel) → synthesis → question gate → characterization →
sufficiency review/fix → question gate → finalize.  Resumable; every AI step is a fresh headless Claude Code session."""
import concurrent.futures as cf, copy, glob, json, os, re, shutil, threading, time

from . import inventory, materials
from .claude import run_claude
from .questions import QuestionStore
from .util import read_json, write_json, read_text, write_text

HERE = os.path.dirname(os.path.abspath(__file__))
PHASES = ['inventory', 'survey', 'units', 'synthesize', 'gate1', 'characterize', 'review', 'gate2', 'finalize']
NEEDS_HUMAN = 10

DEFAULT_CONFIG = {
    'project': 'legacy-system',
    'code': [],            # [{"label": "code", "path": "/abs/path"}]
    'materials': [],       # [{"label": "materials", "path": "/abs/path"}]
    'language': 'Korean',
    'models': {'default': None, 'survey': 'opus', 'unit': 'opus', 'synthesize': 'opus', 'characterize': 'opus',
               'integrate': 'opus', 'review': 'opus', 'fix': 'opus', 'finalize': 'opus', 'oracle': 'sonnet'},
    'parallel': 4,
    'unit_tokens': 20000,             # small focused units → more precise specs (S2: 95% vs 91% with one big unit)
    'group_synthesis_min_units': 9,   # hierarchical synthesis when there are more units than this
    'domains': None,                  # auto-detect: firmware | java_batch | generic
    'characterize': True,
    'review': True,
    'gate_priorities': ['blocking', 'important'],
    'human': 'interactive',   # interactive | file | oracle | none
    'oracle_knowledge': None,
    'oracle_files': None,
    'max_cost_usd': None,     # stop the run (resumable) when the accumulated cost exceeds this
}

ALL_STEPS = ('survey', 'unit', 'synthesize', 'characterize', 'integrate', 'review', 'fix', 'finalize')
PRESETS = {
    # measured on S2 (real SSD firmware, 70-question exam): see experiments/REPORT.md
    'max': {'models': {**{k: 'opus' for k in ALL_STEPS}, 'oracle': 'sonnet'}, 'unit_tokens': 10000,
            'characterize': True, 'review': True},
    'balanced': {'models': {**{k: 'opus' for k in ALL_STEPS}, 'oracle': 'sonnet'}, 'unit_tokens': 20000,
                 'characterize': True, 'review': True},
    'economy': {'models': {**{k: 'sonnet' for k in ALL_STEPS}, 'oracle': 'sonnet'}, 'unit_tokens': 40000,
                'characterize': True, 'review': False},
}

GAP_SCHEMA = {'type': 'object', 'properties': {'gaps': {'type': 'array', 'items': {'type': 'object', 'properties': {
    'id': {'type': 'string'}, 'file': {'type': 'string'}, 'item': {'type': 'string'},
    'type': {'type': 'string'}, 'gap': {'type': 'string'}, 'needed': {'type': 'string'},
    'severity': {'type': 'string', 'enum': ['blocking', 'important', 'minor']}},
    'required': ['id', 'gap', 'needed', 'severity']}}}, 'required': ['gaps']}


class BudgetExceeded(RuntimeError):
    pass


class Pipeline:
    def __init__(self, ws, log=print):
        self.ws = os.path.abspath(ws)
        self.rk = os.path.join(self.ws, '.rekit')
        self.kit = os.path.join(self.ws, 'kit')
        self.log = log
        cfg_path = os.path.join(self.ws, 'rekit.json')
        self.cfg = dict(DEFAULT_CONFIG)
        if os.path.exists(cfg_path):
            user = read_json(cfg_path, {})
            models = dict(DEFAULT_CONFIG['models']); models.update(user.get('models') or {})
            self.cfg.update(user); self.cfg['models'] = models
        self.state_path = os.path.join(self.rk, 'state.json')
        self.state = read_json(self.state_path) or {'phases': {}, 'units': {}, 'sessions': []}
        self._lock = threading.RLock()

    # ---------- infrastructure ----------
    def save_state(self):
        with self._lock:
            snapshot = copy.deepcopy(self.state)
        write_json(self.state_path, snapshot)

    def update_state(self, fn):
        """Mutate state under the lock (worker threads), then persist."""
        with self._lock:
            fn(self.state)
        self.save_state()

    def code_roots(self):
        return [(c['label'], os.path.abspath(c['path'])) for c in self.cfg['code']]

    def material_roots(self):
        return [(m['label'], os.path.abspath(m['path'])) for m in self.cfg['materials']]

    def roots_text(self, roots):
        return ', '.join(f'`{lbl}` = {p}' for lbl, p in roots) or '(none)'

    def render(self, name, **kw):
        t = read_text(os.path.join(HERE, 'prompts', name))
        kw.setdefault('CODE_ROOTS', self.roots_text(self.code_roots()))
        kw.setdefault('MATERIAL_ROOTS', self.roots_text(self.material_roots()))
        kw.setdefault('LANG', self.cfg['language'])
        for k, v in kw.items():
            t = t.replace('{{%s}}' % k, str(v))
        return t

    def claude(self, step, prompt, cwd=None, add_dirs=None, model_key=None, **kw):
        budget = self.cfg.get('max_cost_usd')
        if budget and self.total_cost() >= float(budget):
            raise BudgetExceeded(f'비용 상한(${budget}) 도달: 누적 ${self.total_cost()}. rekit.json의 max_cost_usd를 올리고 다시 실행하세요.')
        model = self.cfg['models'].get(model_key or step.split(':')[0]) or self.cfg['models'].get('default')
        log_path = os.path.join(self.rk, 'logs', re.sub(r'[^\w.-]', '_', step) + '.jsonl')
        dirs = add_dirs if add_dirs is not None else [p for _, p in self.code_roots() + self.material_roots()]
        r = run_claude(prompt, cwd or self.ws, log_path, model=model, add_dirs=dirs, **kw)
        rec = {'step': step, 'cost_usd': r['cost_usd'], 'wall_s': r['wall_s'], 'turns': r['num_turns'],
               'error': r['is_error'], 'model': model}
        self.update_state(lambda s: s['sessions'].append(rec))
        tag = 'ERROR' if r['is_error'] else 'ok'
        self.log(f'  · {step}: {tag} ({r["wall_s"]:.0f}s, ${r["cost_usd"]:.2f})')
        return r

    def phase_done(self, name):
        return self.state['phases'].get(name) == 'done'

    def mark(self, name, status='done'):
        self.state['phases'][name] = status
        self.save_state()

    def total_cost(self):
        with self._lock:
            return round(sum(s.get('cost_usd') or 0 for s in self.state['sessions']), 2)

    # ---------- phases ----------
    def p_inventory(self):
        os.makedirs(os.path.join(self.rk, 'prompts'), exist_ok=True)
        inv = inventory.scan(self.code_roots())
        write_json(os.path.join(self.rk, 'inventory.json'), inv)
        write_text(os.path.join(self.rk, 'inventory.txt'),
            f"# totals: {inv['totals']}\n# languages: {json.dumps(inv['languages'], ensure_ascii=False)}\n"
            f"# build files: {inv['build_files']}\n\n" + inventory.tree_summary(inv, max_lines=3000))
        materials.convert_all(self.material_roots(), os.path.join(self.rk, 'materials_text'))
        write_text(os.path.join(self.rk, 'prompts', 'kitspec.md'), self.render('kitspec.md'))
        intake_p = os.path.join(self.rk, 'intake.md')
        intake_txt = read_text(intake_p, '')
        if not intake_txt or '(답변 없음)' in intake_txt or '(no intake answers)' in intake_txt:
            if self.cfg.get('human') == 'oracle' and self.cfg.get('oracle_knowledge'):
                self.oracle_intake(intake_p)
            elif not os.path.exists(intake_p):
                write_text(intake_p, '# Intake\n(no intake answers)\n')
        os.makedirs(self.kit, exist_ok=True)
        self.log(f"  · inventory: {inv['totals']['files']} files, {inv['totals']['loc']} LOC, ~{inv['totals']['tokens']} tokens")

    def register_inbox(self):
        """Files handed over by humans land in <ws>/materials_inbox: register as material root 'provided' and convert."""
        inbox = os.path.join(self.ws, 'materials_inbox')
        if not os.path.isdir(inbox) or not os.listdir(inbox):
            return
        if not any(m.get('label') == 'provided' for m in self.cfg['materials']):
            self.cfg['materials'].append({'label': 'provided', 'path': inbox})
            cfg_path = os.path.join(self.ws, 'rekit.json')
            user = read_json(cfg_path, {})
            user.setdefault('materials', [])
            if not any(m.get('label') == 'provided' for m in user['materials']):
                user['materials'].append({'label': 'provided', 'path': inbox})
                write_json(cfg_path, user)
        materials.convert_all(self.material_roots(), os.path.join(self.rk, 'materials_text'))

    def p_survey(self):
        r = self.claude('survey', self.render('survey.md', UNIT_TOKENS=self.cfg['unit_tokens']))
        units = self.load_units()
        if not units.get('units'):
            raise RuntimeError('survey did not produce .rekit/units.json')
        self.check_unit_coverage(units)
        QuestionStore(self.ws).ingest_file(os.path.join(self.rk, 'questions', 'survey.json'), 'survey') and None

    def load_units(self):
        p = os.path.join(self.rk, 'units.json')
        return read_json(p) if os.path.exists(p) else {}

    def check_unit_coverage(self, units):
        inv = read_json(os.path.join(self.rk, 'inventory.json'))
        listed = {f for u in units['units'] for f in u.get('files', [])} | {e['file'] for e in units.get('excluded', [])}
        missing = [f"{f['root']}:{f['path']}" for f in inv['files'] if f['kind'] == 'text'
                   and f"{f['root']}:{f['path']}" not in listed]
        if missing:
            units.setdefault('units', []).append({'id': 'MISC', 'title': 'Unassigned files (auto)', 'files': missing,
                                                  'focus': 'files the survey did not assign', 'depends_on': []})
            write_json(os.path.join(self.rk, 'units.json'), units)
            self.log(f'  · {len(missing)} unassigned files put into unit MISC')

    def domains(self):
        if self.cfg.get('domains'):
            return self.cfg['domains']
        inv = read_json(os.path.join(self.rk, 'inventory.json'))
        langs = inv.get('languages', {})
        loc = lambda *ls: sum(langs.get(l, {}).get('loc', 0) for l in ls)
        doms = []
        if loc('c', 'c-header', 'cpp', 'cpp-header', 'asm', 'linker-script') > 0.3 * max(1, inv['totals']['loc']):
            doms.append('firmware')
        if loc('java', 'kotlin', 'groovy', 'jsp') > 0:
            doms.append('java_batch')
        return doms + ['generic']

    def checklist(self):
        parts = []
        for d in self.domains():
            p = os.path.join(HERE, 'prompts', 'checklists', d + '.md')
            if os.path.exists(p):
                parts.append(read_text(p))
        return '\n'.join(parts)

    def p_units(self):
        units = self.load_units()['units']
        todo = [u for u in units if self.state['units'].get(u['id']) != 'done']

        def work(u):
            files = '\n'.join(f'- {f}' for f in u['files'])
            prompt = self.render('unit_v2.md', UNIT_ID=u['id'], UNIT_TITLE=u.get('title', ''), FILES=files,
                                 FOCUS=u.get('focus', ''), CHECKLIST=self.checklist())
            r = self.claude(f"unit:{u['id']}", prompt)
            ok = os.path.exists(os.path.join(self.kit, '05_behavior', f"{u['id']}.md"))
            status = 'done' if ok and not r['is_error'] else 'failed'
            self.update_state(lambda s: s['units'].__setitem__(u['id'], status))
            return u['id'], ok

        with cf.ThreadPoolExecutor(max(1, int(self.cfg['parallel']))) as ex:
            results = list(ex.map(work, todo))
        failed = [uid for uid, ok in results if not ok]
        if failed:
            raise RuntimeError(f'unit analysis failed: {failed} (re-run `rekit run` to retry)')
        store = QuestionStore(self.ws)
        for qf in sorted(glob.glob(os.path.join(self.rk, 'notes', '*', 'questions.json'))):
            store.ingest_file(qf, os.path.basename(os.path.dirname(qf)))
        store.save()

    def p_synthesize(self):
        self.write_answered()
        meta = self.load_units()
        units = meta['units']
        groups = {}
        for u in units:
            groups.setdefault(u.get('group') or 'ALL', []).append(u['id'])
        if len(units) >= int(self.cfg.get('group_synthesis_min_units', 9)) and len(groups) > 1:
            titles = {g['id']: g.get('title', '') for g in meta.get('groups', [])}

            def gsyn(item):
                gid, uids = item
                if os.path.exists(os.path.join(self.rk, 'groups', gid, 'summary.md')):
                    return
                os.makedirs(os.path.join(self.rk, 'groups', gid), exist_ok=True)
                self.claude(f'synthesize_group:{gid}', self.render('synthesize_group.md', GROUP_ID=gid,
                            GROUP_TITLE=titles.get(gid, ''), UNITS=', '.join(uids)), model_key='synthesize')

            with cf.ThreadPoolExecutor(max(1, int(self.cfg['parallel']))) as ex:
                list(ex.map(gsyn, groups.items()))
            sources = ('all `.rekit/groups/*/summary.md`, `.rekit/groups/*/contracts.md`, `.rekit/groups/*/tests.md`, '
                       '`.rekit/groups/*/questions.json` (subsystem syntheses; open `.rekit/notes/<unit>/*` only when '
                       'you need detail)')
        else:
            sources = ('all `.rekit/notes/*/digest.md`, `.rekit/notes/*/contracts.md`, `.rekit/notes/*/tests.md`, '
                       '`.rekit/notes/*/questions.json`')
        self.claude('synthesize', self.render('synthesize_v2.md', SOURCES=sources))
        store = QuestionStore(self.ws)
        store.supersede(os.path.join(self.rk, 'questions', 'merged.json'))
        store.save()

    def write_answered(self):
        store = QuestionStore(self.ws)
        write_json(os.path.join(self.rk, 'questions', 'answered.json'), store.answered_json())

    def p_gate(self, name):
        """Ask humans (or oracle) the open questions of gate priorities; integrate answers into the kit."""
        store = QuestionStore(self.ws)
        for extra in ('characterize.json', 'followup.json') + tuple(
                os.path.basename(p) for p in glob.glob(os.path.join(self.rk, 'questions', 'review_*.json'))):
            p = os.path.join(self.rk, 'questions', extra)
            if os.path.exists(p):
                store.ingest_file(p, extra.split('.')[0])
        store.save()
        prios = tuple(self.cfg['gate_priorities'])
        pending = store.pending(prios)
        mode = self.cfg['human']
        if pending and mode == 'oracle':
            self.answer_with_oracle(store, pending)
        elif pending and mode in ('interactive', 'file'):
            if not self.state.get(f'{name}_asked'):
                self.state[f'{name}_asked'] = True
                self.save_state()
            self.log(f'  · 사람 확인 필요: 질문 {len(pending)}개 (rekit answer 로 답변 후 rekit run 재실행)')
            return NEEDS_HUMAN
        todo = store.to_integrate()
        if todo:
            if any(q.get('files') for q in todo):
                self.register_inbox()
            write_json(os.path.join(self.rk, 'questions', 'to_integrate.json'), todo)
            self.claude(f'integrate:{name}', self.render('integrate.md'), model_key='integrate')
            store = QuestionStore(self.ws)
            store.mark_integrated({q['id'] for q in todo})
            store.ingest_file(os.path.join(self.rk, 'questions', 'followup.json'), 'followup')
            store.save()
        self.write_answered()
        return 0

    def oracle_intake(self, intake_p):
        from .cli import INTAKE_QUESTIONS
        store = QuestionStore(self.ws)
        qs = [{'id': f'Q-INTAKE-{k.upper()}', 'kind': 'question', 'priority': 'important', 'question': q}
              for k, q in INTAKE_QUESTIONS]
        tmp = os.path.join(self.rk, 'questions', 'intake.json')
        write_json(tmp, qs)
        store.ingest_file(tmp, 'intake')
        self.answer_with_oracle(store, [q for q in store.pending() if q['id'].startswith('Q-INTAKE-')])
        by = store.by_id()
        lines = ['# Intake (사람이 제공한 사전 정보)', '']
        for k, q in INTAKE_QUESTIONS:
            item = by.get(f'Q-INTAKE-{k.upper()}', {})
            lines += [f'## {q}', item.get('answer') or '(답변 없음)', '']
            if item.get('status') == 'answered':
                item['integrated'] = True
        store.save()
        write_text(intake_p, '\n'.join(lines))
        self.register_inbox()

    def answer_with_oracle(self, store, pending):
        """Experiment mode: a simulated domain expert answers from a hidden knowledge file."""
        know = read_text(self.cfg['oracle_knowledge'])
        files_dir = self.cfg.get('oracle_files')
        files = []
        if files_dir and os.path.isdir(files_dir):
            files = sorted(os.path.relpath(os.path.join(dp, f), files_dir) for dp, _, fs in os.walk(files_dir) for f in fs)
        qs = [{k: q.get(k) for k in ('id', 'kind', 'question', 'context', 'options')} for q in pending]
        prompt = read_text(os.path.join(HERE, 'prompts', 'oracle.md')) \
            .replace('{{KNOWLEDGE}}', know).replace('{{FILES}}', '\n'.join(files) or '(none)') \
            .replace('{{QUESTIONS}}', json.dumps(qs, ensure_ascii=False, indent=1))
        schema = {'type': 'object', 'properties': {'answers': {'type': 'array', 'items': {'type': 'object', 'properties': {
            'id': {'type': 'string'}, 'answer': {'type': 'string'}, 'files': {'type': 'array', 'items': {'type': 'string'}}},
            'required': ['id', 'answer']}}}, 'required': ['answers']}
        tmp = os.path.join(self.rk, 'oracle_cwd')
        os.makedirs(tmp, exist_ok=True)
        r = self.claude('oracle', prompt, cwd=tmp, add_dirs=[], model_key='oracle', json_schema=schema,
                        allowed_tools=['Read'])
        answers = (r.get('structured') or {}).get('answers') or []
        inbox = os.path.join(self.ws, 'materials_inbox')
        valid = store.by_id()
        for a in answers:
            if a.get('id') not in valid:
                continue
            got = []
            for f in a.get('files') or []:
                src = os.path.join(files_dir or '', f)
                if files_dir and os.path.exists(src):
                    dst = os.path.join(inbox, f)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
                    got.append(dst)
            store.record_answer(a['id'], a['answer'], by='oracle', files=got)
        for q in pending:
            if store.by_id()[q['id']]['status'] == 'open':
                store.defer(q['id'], 'oracle gave no answer')
        store.save()
        self.log(f'  · oracle answered {len(answers)} of {len(pending)} questions')

    def p_characterize(self):
        if not self.cfg.get('characterize'):
            return
        self.claude('characterize', self.render('characterize.md'), timeout_s=4 * 3600)

    def p_review(self):
        if not self.cfg.get('review'):
            return
        units = self.load_units()['units']
        rv = os.path.join(self.rk, 'review')
        os.makedirs(rv, exist_ok=True)
        # kit-only sandbox: the reviewer must not see the code
        box = os.path.join(self.rk, 'review_box')
        shutil.rmtree(box, ignore_errors=True)
        shutil.copytree(self.kit, box)
        areas = [('SYS', 'README.md (if any), 00_overview.md, 02_architecture.md, 03_interfaces/, 04_data/, 06_nfr.md')] + \
                [(u['id'], f"05_behavior/{u['id']}.md and the 03_interfaces/04_data/07_tests files it references") for u in units]

        def review(area):
            aid, files = area
            out = os.path.join(rv, f'gaps_{aid}.json')
            if os.path.exists(out):
                return aid
            r = self.claude(f'review:{aid}', self.render('review_v2.md', AREA=aid, AREA_ID=aid, FILES=files),
                            cwd=box, add_dirs=[], allowed_tools=['Read', 'Glob', 'Grep'], json_schema=GAP_SCHEMA)
            gaps = (r.get('structured') or {}).get('gaps')
            if gaps is None:
                m = re.search(r'\[.*\]', r['result'] or '', re.S)
                try:
                    gaps = json.loads(m.group(0)) if m else []
                except Exception:
                    gaps = []
            write_json(out, gaps)
            return aid

        with cf.ThreadPoolExecutor(max(1, int(self.cfg['parallel']))) as ex:
            list(ex.map(review, areas))

        # Fix gaps in batches (one session per subsystem group, SYS gaps first), sequentially: fixes edit shared
        # interface/data files, and one session per batch keeps the context and avoids conflicting edits.
        group_of = {u['id']: (u.get('group') or 'ALL') for u in units}
        batches = {}
        for aid, _ in areas:
            gp = os.path.join(rv, f'gaps_{aid}.json')
            gaps = [g for g in (read_json(gp) or []) if g.get('severity') in ('blocking', 'important')]
            if gaps:
                key = 'SYS' if aid == 'SYS' else group_of.get(aid, 'ALL')
                batches.setdefault(key, []).extend(gaps)
        for key in sorted(batches, key=lambda k: (k != 'SYS', k)):
            if os.path.exists(os.path.join(rv, f'fixed_{key}.json')):
                continue
            write_json(os.path.join(rv, f'batch_{key}.json'), batches[key])
            self.claude(f'fix:{key}', self.render('fix.md', BATCH=key))
        shutil.rmtree(box, ignore_errors=True)

    def p_finalize(self):
        self.coverage()
        self.claude('finalize', self.render('finalize.md'))
        QuestionStore(self.ws).save()   # re-render 09_open_questions.md
        self.coverage()

    def coverage(self):
        inv = read_json(os.path.join(self.rk, 'inventory.json'))
        units = self.load_units()
        excluded = {e['file'] for e in units.get('excluded', [])}
        kit_text = ''
        for p in glob.glob(os.path.join(self.kit, '**', '*'), recursive=True):
            if os.path.isfile(p) and p.endswith(('.md', '.json', '.txt')):
                kit_text += open(p, encoding='utf-8', errors='replace').read() + '\n'
        files = [f for f in inv['files'] if f['kind'] == 'text' and f"{f['root']}:{f['path']}" not in excluded]
        unref_files = [f"{f['root']}:{f['path']}" for f in files if f['path'] not in kit_text]
        syms = [(f"{f['root']}:{f['path']}", s) for f in files for s in f.get('symbols', [])]
        unref_syms = [f'{p}#{s}' for p, s in syms if not re.search(r'\b' + re.escape(s) + r'\b', kit_text)]
        cov = {'files_total': len(files), 'files_referenced': len(files) - len(unref_files),
               'symbols_total': len(syms), 'symbols_referenced': len(syms) - len(unref_syms),
               'unreferenced_files': unref_files, 'unreferenced_symbols': unref_syms[:500],
               'kit_bytes': len(kit_text.encode('utf-8')), 'kit_tokens_est': int(len(kit_text.encode('utf-8')) / 3.6)}
        write_json(os.path.join(self.rk, 'coverage.json'), cov)
        return cov

    # ---------- driver ----------
    def run(self, until=None):
        steps = {'inventory': self.p_inventory, 'survey': self.p_survey, 'units': self.p_units,
                 'synthesize': self.p_synthesize, 'gate1': lambda: self.p_gate('gate1'),
                 'characterize': self.p_characterize, 'review': self.p_review,
                 'gate2': lambda: self.p_gate('gate2'), 'finalize': self.p_finalize}
        last = PHASES.index(until) if until in PHASES else len(PHASES) - 1
        for name in PHASES[:last + 1]:
            if self.phase_done(name):
                continue
            self.log(f'▶ {name}')
            self.mark(name, 'running')
            t0 = time.time()
            rc = steps[name]()
            if rc == NEEDS_HUMAN:
                self.mark(name, 'waiting_human')
                return NEEDS_HUMAN
            self.mark(name, 'done')
            self.log(f'  ✓ {name} ({time.time() - t0:.0f}s, 누적 ${self.total_cost()})')
        return 0
