"""Question store: collect AI-raised questions, ask humans (terminal / Markdown file / Claude Code front-end / oracle),
and hand answers back to the pipeline."""
import glob, json, os, re, shutil, textwrap, time

from .util import read_json, write_json, write_text, read_text

PRIO = {'blocking': 0, 'important': 1, 'minor': 2}


class QuestionStore:
    def __init__(self, ws):
        self.ws = ws
        self.dir = os.path.join(ws, '.rekit', 'questions')
        os.makedirs(self.dir, exist_ok=True)
        self.path = os.path.join(self.dir, 'store.json')
        self.items = read_json(self.path, [])

    def save(self):
        write_json(self.path, self.items)
        self.render_markdown()

    def by_id(self):
        return {q['id']: q for q in self.items}

    # ---------- collection ----------
    def ingest_file(self, path, source):
        data = read_json(path)
        if data is None:
            return 0
        if isinstance(data, dict):
            data = data.get('questions', [])
        idx, n = self.by_id(), 0
        for q in data:
            if not isinstance(q, dict) or not q.get('question'):
                continue
            qid = q.get('id') or f'Q-{source.upper()}-{len(self.items) + 1:02d}'
            if qid in idx:
                old = idx[qid]
                if old.get('status') == 'open':
                    for k in ('question', 'context', 'why', 'options', 'assumption', 'priority', 'affects'):
                        if q.get(k):
                            old[k] = q[k]
                continue
            q = dict(q)
            q['id'] = qid
            q.setdefault('kind', 'question')
            q.setdefault('priority', 'important')
            q['source'] = source
            q['status'] = 'open'
            self.items.append(q)
            idx[qid] = q
            n += 1
        return n

    def supersede(self, merged_path):
        """After synthesis: questions not present in merged (and not answered) are marked merged/dropped."""
        merged = read_json(merged_path)
        if not isinstance(merged, list):
            return
        keep = {q.get('id') for q in merged if isinstance(q, dict)}
        merged_from = {m for q in merged if isinstance(q, dict) for m in (q.get('merged_from') or [])}
        for q in self.items:
            if q['status'] == 'open' and q['id'] not in keep:
                q['status'] = 'merged' if q['id'] in merged_from else 'dropped'
        self.ingest_file(merged_path, 'merged')

    def pending(self, priorities=('blocking', 'important', 'minor')):
        out = [q for q in self.items if q['status'] == 'open' and q.get('priority', 'important') in priorities]
        return sorted(out, key=lambda q: (PRIO.get(q.get('priority'), 1), q['id']))

    def record_answer(self, qid, answer, by='human', files=()):
        q = self.by_id()[qid]
        q['status'] = 'answered'
        q['answer'] = answer
        q['answered_by'] = by
        q['answered_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        if files:
            q['files'] = list(files)
        q['integrated'] = False

    def defer(self, qid, note=''):
        q = self.by_id()[qid]
        q['status'] = 'deferred'
        q['answer'] = note

    def to_integrate(self):
        return [q for q in self.items if q['status'] == 'answered' and not q.get('integrated')]

    def mark_integrated(self, ids):
        for q in self.items:
            if q['id'] in ids:
                q['integrated'] = True

    def answered_json(self):
        return [{'id': q['id'], 'question': q['question'], 'answer': q.get('answer')}
                for q in self.items if q['status'] == 'answered']

    # ---------- rendering ----------
    def render_markdown(self, path=None):
        path = path or os.path.join(self.ws, 'kit', '09_open_questions.md')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        lines = ['# 미해결 질문 및 적용 가정', '',
                 '> rekit이 자동 생성합니다. 답변은 `rekit answer` 또는 Claude Code `/rekit:answer`로 입력하세요.', '']
        groups = [('open', '미해결'), ('deferred', '보류(답변 불가/나중에)'), ('answered', '답변 완료')]
        for st, title in groups:
            qs = [q for q in self.items if q['status'] == st]
            if not qs:
                continue
            lines += [f'## {title} ({len(qs)})', '']
            for q in sorted(qs, key=lambda q: (PRIO.get(q.get('priority'), 1), q['id'])):
                lines.append(f"### {q['id']} [{q.get('priority', '')}] {q.get('area', '')}")
                lines.append(f"- 질문: {q['question']}")
                if q.get('context'):
                    lines.append(f"- 배경: {q['context']}")
                if q.get('why'):
                    lines.append(f"- 영향: {q['why']}")
                if q.get('options'):
                    lines.append('- 선택지: ' + ' / '.join(str(o) for o in q['options']))
                if q.get('assumption'):
                    lines.append(f"- 현재 적용 가정: {q['assumption']}")
                if q.get('answer'):
                    lines.append(f"- 답변: {q['answer']}")
                lines.append('')
        write_text(path, '\n'.join(lines))

    def _attach_paths(self, text):
        """Copy files/dirs whose existing paths appear in an answer into <ws>/materials_inbox (answers given by file)."""
        inbox = os.path.join(self.ws, 'materials_inbox')
        got = []
        for tok in re.findall(r'(?:~|/|\./|\.\./)[^\s,;"\'`]+', text):
            src = os.path.expanduser(tok.rstrip('.)'))
            if os.path.exists(src) and not os.path.abspath(src).startswith(self.ws):
                os.makedirs(inbox, exist_ok=True)
                dst = os.path.join(inbox, os.path.basename(src.rstrip('/')))
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
                got.append(dst)
        return got

    def export_for_humans(self, path):
        """Markdown questionnaire that a domain expert can fill in offline."""
        qs = self.pending()
        out = ['# 레거시 재개발을 위한 확인 요청', '',
               '각 질문의 `답변:` 줄 아래에 답을 적어 주세요. 모르면 "모름", 나중에 답할 것은 "보류"라고 적어 주세요.',
               '자료(파일)로 답하는 경우 파일 경로를 적어 주세요.', '']
        for q in qs:
            out += [f"## {q['id']} ({q.get('priority', '')})", '', q['question'], '']
            if q.get('context'):
                out += [f"배경: {q['context']}", '']
            if q.get('options'):
                out += ['선택지:'] + [f'  {i + 1}. {o}' for i, o in enumerate(q['options'])] + ['']
            if q.get('assumption'):
                out += [f"(답이 없으면 적용할 가정: {q['assumption']})", '']
            out += ['답변:', '', '']
        write_text(path, '\n'.join(out))
        return len(qs)

    def import_from_humans(self, path):
        text = read_text(path, '')
        parts = re.split(r'^## (Q-[\w-]+)[^\n]*$', text, flags=re.M)
        n = 0
        idx = self.by_id()
        for i in range(1, len(parts), 2):
            qid, body = parts[i], parts[i + 1]
            m = re.search(r'^답변:\s*(.*)$', body, flags=re.M | re.S)
            ans = (m.group(1).strip() if m else '').strip()
            if not ans or qid not in idx or idx[qid]['status'] != 'open':
                continue
            if ans in ('보류', 'defer', '모름'):
                self.defer(qid, ans)
            else:
                opts = idx[qid].get('options') or []
                if ans.isdigit() and 1 <= int(ans) <= len(opts):
                    ans = opts[int(ans) - 1]
                files = self._attach_paths(ans)
                self.record_answer(qid, ans, by='human-file', files=files)
            n += 1
        return n


def ask_terminal(store, priorities=('blocking', 'important', 'minor'), materials_inbox=None):
    """Interactive Korean Q&A in a terminal. Returns number answered."""
    qs = store.pending(priorities)
    if not qs:
        print('대기 중인 질문이 없습니다.')
        return 0
    print(f'\n확인이 필요한 질문 {len(qs)}개가 있습니다. (번호/자유 입력, s=보류, f 경로=파일로 답변, q=중단)\n')
    n = 0
    for i, q in enumerate(qs, 1):
        print('=' * 78)
        print(f"[{i}/{len(qs)}] {q['id']}  우선순위: {q.get('priority')}  영역: {q.get('area', '')}")
        print(textwrap.fill(q['question'], 78))
        for label, key in (('배경', 'context'), ('영향', 'why'), ('현재 가정', 'assumption')):
            if q.get(key):
                print(textwrap.fill(f'{label}: {q[key]}', 78, subsequent_indent='  '))
        for j, o in enumerate(q.get('options') or [], 1):
            print(f'  {j}) {o}')
        try:
            ans = input('답변> ').strip()
        except EOFError:
            break
        if ans == 'q':
            break
        if not ans or ans == 's':
            store.defer(q['id'], '보류(터미널)')
        elif ans.startswith('f '):
            src = os.path.expanduser(ans[2:].strip())
            files = []
            if materials_inbox and os.path.exists(src):
                os.makedirs(materials_inbox, exist_ok=True)
                dst = os.path.join(materials_inbox, os.path.basename(src))
                (shutil.copytree if os.path.isdir(src) else shutil.copy2)(src, dst)
                files.append(dst)
            store.record_answer(q['id'], f'자료 제공: {src}', files=files)
        else:
            opts = q.get('options') or []
            if ans.isdigit() and 1 <= int(ans) <= len(opts):
                ans = opts[int(ans) - 1]
            store.record_answer(q['id'], ans)
        n += 1
        store.save()
    store.save()
    return n
