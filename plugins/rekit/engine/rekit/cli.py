"""rekit command line.

  rekit init <workspace> --code <dir> [--code <dir>...] [--materials <dir|file>...] [--name NAME] [--no-intake]
  rekit run [<workspace>] [--until PHASE] [--human interactive|file|oracle|none]
  rekit status [<workspace>]
  rekit questions [<workspace>] [--export FILE] [--json]
  rekit answer [<workspace>] [--import FILE] [--set QID "answer"] [--defer QID]
  rekit add-material [<workspace>] <file|dir>...
  rekit coverage [<workspace>]
  rekit similarity <legacy_code_dir> <new_code_dir> [--contract GLOB ...] [--json] [--detail]
Exit codes: 0 done/ok, 10 waiting for human answers, 1 error.
"""
import argparse, json, os, shutil, sys

from .pipeline import Pipeline, PHASES, NEEDS_HUMAN, DEFAULT_CONFIG, PRESETS
from .questions import QuestionStore, ask_terminal
from .util import read_json, write_json, write_text

INTAKE_QUESTIONS = [
    ('goal', '재개발의 목적/배경은 무엇인가요? (예: 플랫폼 교체, 유지보수성, 성능, 단종 대응)'),
    ('target', '목표 기술 스택/플랫폼이 정해져 있나요? (예: Java 21 + Spring Boot 3, 신규 SoC + C11, 미정)'),
    ('arch', '새 시스템의 구조(아키텍처)에 대한 요구나, 레거시 구조에서 반드시 고치고 싶은 점이 있나요? (예: 전역 상태 제거, 계층 분리, 멀티코어/멀티 인스턴스 대응, 테스트 용이성, 모듈 경계 / 없음·모름)'),
    ('compat', '반드시 그대로 유지해야 하는 것은? (외부 인터페이스, 파일/전문 포맷, DB 스키마, 온플래시 데이터 포맷, 프로토콜, 성능 등 / 모름)'),
    ('scope', '재개발 범위에서 제외할 기능/모듈이 있나요? (예: 사용하지 않는 배치, 특정 #ifdef 변형)'),
    ('env', '레거시를 빌드/실행해 볼 수 있는 환경·장비·시뮬레이터·테스트 데이터(샘플 입력, 덤프, 로그)가 있나요?'),
    ('prodcfg', '운영(양산) 환경에서만 적용되는 설정의 실제 값이나 파일을 줄 수 있나요? (예: JVM 옵션·시스템 프로퍼티, 환경변수, 운영 설정 파일, 릴리스 빌드 스크립트·컴파일 플래그, 스케줄러/crontab 설정) — 코드 기본값과 다를 수 있어 가장 중요합니다'),
    ('people', '질문에 답해 줄 수 있는 사람(역할)은 누구인가요? (예: 운영 담당, 현업, 원 개발자)'),
]


def ws_arg(p):
    return os.path.abspath(p or os.getcwd())


def cmd_init(a):
    ws = os.path.abspath(a.workspace)
    os.makedirs(ws, exist_ok=True)
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    cfg['project'] = a.name or os.path.basename(ws)
    cfg['code'] = [{'label': f'code{i + 1}' if len(a.code) > 1 else 'code', 'path': os.path.abspath(p)} for i, p in enumerate(a.code)]
    cfg['materials'] = [{'label': f'materials{i + 1}' if len(a.materials) > 1 else 'materials', 'path': os.path.abspath(p)}
                        for i, p in enumerate(a.materials or [])]
    for c in cfg['code'] + cfg['materials']:
        if not os.path.exists(c['path']):
            sys.exit(f"경로가 없습니다: {c['path']}")
    if a.lang:
        cfg['language'] = a.lang
    preset = PRESETS[a.preset]
    cfg['preset'] = a.preset
    cfg['models'] = dict(preset['models'])
    for k in ('unit_tokens', 'characterize', 'review'):
        cfg[k] = preset[k]
    if a.budget:
        cfg['max_cost_usd'] = a.budget
    write_json(os.path.join(ws, 'rekit.json'), cfg)
    os.makedirs(os.path.join(ws, '.rekit'), exist_ok=True)
    intake = ['# Intake (사람이 제공한 사전 정보)', '']
    answers = json.loads(a.intake_json) if a.intake_json else {}
    if not a.no_intake and not answers and sys.stdin.isatty():
        print('사전 질문 (모르면 Enter):')
        for key, q in INTAKE_QUESTIONS:
            answers[key] = input(f'- {q}\n> ').strip()
    for key, q in INTAKE_QUESTIONS:
        intake += [f'## {q}', answers.get(key) or '(답변 없음)', '']
    write_text(os.path.join(ws, '.rekit', 'intake.md'), '\n'.join(intake))
    print(f'워크스페이스 생성: {ws}\n다음: rekit run {ws}')


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def run_state(ws):
    """running | waiting_human | done | failed | idle — based on pid file and last run record."""
    pidf = os.path.join(ws, '.rekit', 'run.pid')
    if os.path.exists(pidf):
        try:
            if _pid_alive(int(open(pidf).read().strip())):
                return 'running'
        except ValueError:
            pass
    last = os.path.join(ws, '.rekit', 'last_run.json')
    if os.path.exists(last):
        rc = (read_json(last) or {}).get('exit_code')
        if rc == 0:
            phases = (read_json(os.path.join(ws, '.rekit', 'state.json')) or {}).get('phases', {})
            return 'done' if all(phases.get(ph) == 'done' for ph in PHASES) else 'paused'
        return {NEEDS_HUMAN: 'waiting_human'}.get(rc, 'failed')
    return 'idle'


def cmd_run(a):
    ws = ws_arg(a.workspace)
    if a.bg:
        import subprocess, time
        if run_state(ws) == 'running':
            print('이미 실행 중입니다.'); return 0
        args = [sys.executable, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'rekit.py'),
                'run', ws]
        for opt, val in (('--until', a.until), ('--human', a.human), ('--oracle', a.oracle),
                         ('--oracle-files', a.oracle_files), ('--parallel', a.parallel)):
            if val:
                args += [opt, str(val)]
        for ph in (a.redo or []):
            args += ['--redo', ph]
        logf = open(os.path.join(ws, '.rekit', 'run.log'), 'a')
        logf.write(f"\n===== run started {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n"); logf.flush()
        proc = subprocess.Popen(args, stdout=logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                start_new_session=True, cwd=ws)
        for _ in range(50):                      # wait until the child registered itself
            if run_state(ws) == 'running':
                break
            time.sleep(0.1)
        print(f'백그라운드 실행 시작 (pid {proc.pid}). 진행상황: rekit status {ws}  / 로그: {ws}/.rekit/run.log')
        return 0
    import time
    if run_state(ws) == 'running':
        pid = open(os.path.join(ws, '.rekit', 'run.pid')).read().strip()
        if pid != str(os.getpid()):
            print(f'이미 다른 실행(pid {pid})이 진행 중입니다. rekit status {ws}')
            return 1
    pidf = os.path.join(ws, '.rekit', 'run.pid')
    last = os.path.join(ws, '.rekit', 'last_run.json')
    write_text(pidf, str(os.getpid()))
    if os.path.exists(last):
        os.remove(last)
    try:
        rc = _cmd_run(a, ws)
    finally:
        if os.path.exists(pidf) and open(pidf).read().strip() == str(os.getpid()):
            os.remove(pidf)
    write_json(last, {'exit_code': rc, 'finished_at': time.strftime('%Y-%m-%d %H:%M:%S')})
    return rc


def _cmd_run(a, ws):
    p = Pipeline(ws)
    if a.human:
        p.cfg['human'] = a.human
    if a.oracle:
        p.cfg['human'] = 'oracle'
        p.cfg['oracle_knowledge'] = os.path.abspath(a.oracle)
    if a.oracle_files:
        p.cfg['oracle_files'] = os.path.abspath(a.oracle_files)
    if a.parallel:
        p.cfg['parallel'] = a.parallel
    if a.human or a.oracle or a.oracle_files or a.parallel:   # persist so that resumed runs behave the same
        cfg_path = os.path.join(ws, 'rekit.json')
        user = read_json(cfg_path, {})
        for k in ('human', 'oracle_knowledge', 'oracle_files', 'parallel'):
            if p.cfg.get(k) is not None:
                user[k] = p.cfg[k]
        write_json(cfg_path, user)
    for ph in (a.redo or []):
        p.state['phases'].pop(ph, None)
    p.save_state()
    try:
        rc = p.run(until=a.until)
    except Exception as e:
        print(f'오류: {e}', file=sys.stderr)
        return 1
    if rc == NEEDS_HUMAN:
        store = QuestionStore(ws)
        n = len(store.pending(tuple(p.cfg['gate_priorities'])))
        print(f'\n[대기] 사람의 확인이 필요한 질문 {n}개. `rekit answer {ws}` 로 답한 뒤 `rekit run {ws}` 를 다시 실행하세요.')
        return NEEDS_HUMAN
    if not all(p.phase_done(ph) for ph in PHASES):
        nxt = next(ph for ph in PHASES if not p.phase_done(ph))
        print(f"\n[일시정지] '{a.until or nxt}' 단계까지 실행했습니다. 다음 단계: {nxt}. 계속하려면: rekit run {ws}")
        return 0
    cov = p.coverage() if os.path.exists(os.path.join(ws, '.rekit', 'inventory.json')) else {}
    print(f"\n[완료] 키트: {os.path.join(ws, 'kit')}  누적 비용 ${p.total_cost()}  "
          f"파일 커버리지 {cov.get('files_referenced')}/{cov.get('files_total')}, 심볼 {cov.get('symbols_referenced')}/{cov.get('symbols_total')}")
    return 0


def cmd_status(a):
    ws = ws_arg(a.workspace)
    p = Pipeline(ws)
    st = p.state
    print(f"프로젝트: {p.cfg['project']}   상태: {run_state(ws)}   누적 비용: ${p.total_cost()}")
    for ph in PHASES:
        print(f"  {ph:13s} {st['phases'].get(ph, '-')}")
    if st.get('units'):
        done = sum(1 for v in st['units'].values() if v == 'done')
        print(f"  units: {done}/{len(p.load_units().get('units', []))} done")
    store = QuestionStore(ws)
    by = {}
    for q in store.items:
        by[q['status']] = by.get(q['status'], 0) + 1
    print(f'  questions: {by}')
    if a.json:
        print(json.dumps({'run_state': run_state(ws), 'phases': st['phases'], 'units': st.get('units'),
                          'questions': by, 'cost': p.total_cost()}))


def cmd_questions(a):
    ws = ws_arg(a.workspace)
    store = QuestionStore(ws)
    if a.export:
        n = store.export_for_humans(a.export)
        print(f'{n}개 질문을 {a.export} 로 내보냈습니다.')
        return
    pend = store.pending()
    if a.json:
        print(json.dumps(pend, ensure_ascii=False, indent=1))
        return
    for q in pend:
        print(f"{q['id']} [{q.get('priority')}] {q['question']}")
        for i, o in enumerate(q.get('options') or [], 1):
            print(f'    {i}) {o}')


def cmd_answer(a):
    ws = ws_arg(a.workspace)
    store = QuestionStore(ws)
    inbox = os.path.join(ws, 'materials_inbox')
    if a.import_file:
        n = store.import_from_humans(a.import_file)
        store.save()
        print(f'{n}개 답변을 가져왔습니다.')
        return
    if a.set:
        qid, ans = a.set
        files = []
        for f in a.file or []:
            os.makedirs(inbox, exist_ok=True)
            dst = os.path.join(inbox, os.path.basename(f.rstrip('/')))
            (shutil.copytree if os.path.isdir(f) else shutil.copy2)(f, dst)
            files.append(dst)
        store.record_answer(qid, ans, files=files)
        store.save()
        print(f'{qid} 답변 저장')
        return
    if a.defer:
        store.defer(a.defer, '보류')
        store.save()
        return
    ask_terminal(store, materials_inbox=inbox)


def cmd_add_material(a):
    ws = ws_arg(a.workspace)
    inbox = os.path.join(ws, 'materials_inbox')
    os.makedirs(inbox, exist_ok=True)
    for f in a.paths:
        dst = os.path.join(inbox, os.path.basename(f.rstrip('/')))
        (shutil.copytree if os.path.isdir(f) else shutil.copy2)(f, dst)
    cfg_path = os.path.join(ws, 'rekit.json')
    cfg = read_json(cfg_path, {})
    if not any(m['label'] == 'provided' for m in cfg['materials']):
        cfg['materials'].append({'label': 'provided', 'path': inbox})
        write_json(cfg_path, cfg)
    from . import materials
    materials.convert_all([(m['label'], m['path']) for m in cfg['materials']], os.path.join(ws, '.rekit', 'materials_text'))
    print(f'{len(a.paths)}개 자료 추가 완료 (다음 rekit run 에 반영)')


def cmd_doctor(a):
    import importlib, platform, shutil, subprocess
    rows = []
    ok_py = sys.version_info >= (3, 9)
    rows.append(('python', platform.python_version(), ok_py, '3.9 이상 필요'))
    try:
        v = subprocess.run(['claude', '--version'], capture_output=True, text=True, timeout=60).stdout.strip()
        rows.append(('claude CLI', v or '?', bool(v), 'Claude Code 설치·로그인 필요 (https://code.claude.com)'))
    except Exception:
        rows.append(('claude CLI', '없음', False, 'Claude Code 설치·로그인 필요'))
    for tool, why in (('pdftotext', 'PDF 변환(없으면 pypdf 사용)'), ('pandoc', 'DOCX 대체 변환'),
                      ('soffice', 'DOC/XLS/PPT/HWP 변환'), ('hwp5txt', 'HWP 변환 (pip install pyhwp)')):
        rows.append((tool, shutil.which(tool) or '없음', bool(shutil.which(tool)), why))
    for mod, why in (('docx', 'python-docx: DOCX'), ('openpyxl', 'XLSX'), ('pptx', 'python-pptx: PPTX'), ('pypdf', 'PDF 대체')):
        try:
            importlib.import_module(mod)
            rows.append((mod, '있음', True, why))
        except Exception:
            rows.append((mod, '없음', False, why + ' (pip install 로 설치 권장)'))
    for name, val, ok, why in rows:
        print(f"{'OK ' if ok else '-- '} {name:12s} {val:40.40s} {'' if ok else why}")
    if not (ok_py and rows[1][2]):
        print('\n필수 조건이 충족되지 않았습니다.')
        return 1
    print('\n필수 조건 충족. (-- 표시는 선택 항목: 해당 형식 자료가 있을 때만 필요)')
    return 0


def cmd_wait(a):
    """Block until the run is no longer running (for front-ends): prints the final state and pending question count."""
    import time
    ws = ws_arg(a.workspace)
    t0 = time.time()
    while run_state(ws) == 'running' and time.time() - t0 < a.timeout:
        time.sleep(a.interval)
    st = run_state(ws)
    n = len(QuestionStore(ws).pending()) if st == 'waiting_human' else 0
    print(json.dumps({'run_state': st, 'pending_questions': n, 'waited_s': int(time.time() - t0)}, ensure_ascii=False))
    return 0


def cmd_coverage(a):
    print(json.dumps({k: v for k, v in Pipeline(ws_arg(a.workspace)).coverage().items() if not k.startswith('unref')}, indent=1))


def cmd_similarity(a):
    from . import similarity
    r = similarity.compare(a.legacy, a.new, a.contract or (), detail=a.detail)
    print(json.dumps(r, ensure_ascii=False, indent=1) if a.json or a.detail else similarity.format_report(r))
    return 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):      # progress lines must reach run.log / redirected files immediately
        try:
            stream.reconfigure(line_buffering=True)
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog='rekit', description='레거시 코드+자료 → AI 재개발용 키트 생성기')
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('init'); s.add_argument('workspace'); s.add_argument('--code', action='append', required=True)
    s.add_argument('--materials', action='append'); s.add_argument('--name'); s.add_argument('--lang')
    s.add_argument('--no-intake', action='store_true'); s.add_argument('--intake-json')
    s.add_argument('--preset', choices=sorted(PRESETS), default='balanced',
                   help='max: 최고 정밀(Opus·작은 단위) / balanced: 기본 / economy: 저비용(Sonnet)')
    s.add_argument('--budget', type=float, help='비용 상한(USD). 넘으면 멈추고 재개 가능')
    s.set_defaults(fn=cmd_init)
    s = sub.add_parser('run'); s.add_argument('workspace', nargs='?'); s.add_argument('--until', choices=PHASES)
    s.add_argument('--human', choices=['interactive', 'file', 'oracle', 'none']); s.add_argument('--oracle')
    s.add_argument('--oracle-files'); s.add_argument('--parallel', type=int); s.add_argument('--redo', action='append', choices=PHASES)
    s.add_argument('--bg', action='store_true', help='detach and run in background (pid/log in .rekit/)')
    s.set_defaults(fn=cmd_run)
    s = sub.add_parser('status'); s.add_argument('workspace', nargs='?'); s.add_argument('--json', action='store_true'); s.set_defaults(fn=cmd_status)
    s = sub.add_parser('questions'); s.add_argument('workspace', nargs='?'); s.add_argument('--export'); s.add_argument('--json', action='store_true')
    s.set_defaults(fn=cmd_questions)
    s = sub.add_parser('answer'); s.add_argument('workspace', nargs='?'); s.add_argument('--import', dest='import_file')
    s.add_argument('--set', nargs=2, metavar=('QID', 'ANSWER')); s.add_argument('--file', action='append'); s.add_argument('--defer')
    s.set_defaults(fn=cmd_answer)
    s = sub.add_parser('add-material'); s.add_argument('workspace'); s.add_argument('paths', nargs='+'); s.set_defaults(fn=cmd_add_material)
    s = sub.add_parser('coverage'); s.add_argument('workspace', nargs='?'); s.set_defaults(fn=cmd_coverage)
    s = sub.add_parser('similarity', help='신규 구현이 레거시 구조를 얼마나 닮았는지(LSS) 측정')
    s.add_argument('legacy'); s.add_argument('new')
    s.add_argument('--contract', action='append', help='그대로 유지해야 하는 계약 파일 glob (예: fw_api.h, hal/*.h)')
    s.add_argument('--json', action='store_true'); s.add_argument('--detail', action='store_true')
    s.set_defaults(fn=cmd_similarity)
    s = sub.add_parser('doctor', help='필수/선택 도구 점검'); s.set_defaults(fn=cmd_doctor)
    s = sub.add_parser('wait', help='실행이 멈출 때까지 대기(완료/사람 확인 필요/실패/일시정지)')
    s.add_argument('workspace', nargs='?'); s.add_argument('--timeout', type=int, default=6600)
    s.add_argument('--interval', type=int, default=30); s.set_defaults(fn=cmd_wait)
    a = ap.parse_args(argv)
    rc = a.fn(a)
    sys.exit(rc or 0)
