---
description: rekit 엔진이 사람에게 확인을 요청한 질문(운영 설정, 의도, 문서-코드 불일치, 자료 요청 등)을 대화형으로 묻고 답을 기록한 뒤 분석을 재개한다.
argument-hint: "[작업폴더]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/engine/rekit.py *), Bash(ls *), Read, AskUserQuestion
---

엔진(이하 `RK`): `python3 ${CLAUDE_PLUGIN_ROOT}/engine/rekit.py`

1. 작업폴더: `$ARGUMENTS` 또는 현재 디렉터리의 `rekit-work/*/rekit.json`.
2. `RK questions <ws> --json`으로 대기 질문을 가져온다. 없으면 그렇게 알리고 끝낸다.
3. AskUserQuestion으로 최대 4개씩 묻는다.
   - header: 영역(12자 이내). question: 질문 + 배경/영향 1~2문장(코드를 읽지 않는 사람도 이해하도록).
   - options: 질문의 `options` 2~4개(길면 요약), "모름/나중에" 선택지 포함. 사용자는 Other로 자유 입력 가능.
   - `kind == material_request`이면 파일/폴더 경로를 받는다.
4. 기록:
   - `RK answer <ws> --set <QID> "<답변>"` (자료면 `--file <경로>` 추가, 여러 개면 반복)
   - 모름/보류: `RK answer <ws> --defer <QID>`
   - 다른 담당자에게 물어야 하면: `RK questions <ws> --export <ws>/질문지.md` 후 전달, 작성본은 `RK answer <ws> --import <파일>`
5. 끝나면 `RK run <ws> --bg`로 분석을 재개하고, `/rekit:status`로 확인할 수 있다고 알린다.
사용자 대신 추측해서 답하지 않는다.
