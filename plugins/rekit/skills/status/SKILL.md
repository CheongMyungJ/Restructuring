---
description: rekit 재개발 키트 생성 작업의 진행 상태(단계, 단위 분석 진행률, 질문, 비용)를 보여준다.
argument-hint: "[작업폴더]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/engine/rekit.py *), Bash(ls *), Bash(tail *)
---

엔진: `python3 ${CLAUDE_PLUGIN_ROOT}/engine/rekit.py`

1. 작업폴더: `$ARGUMENTS`가 있으면 그것, 없으면 현재 디렉터리의 `rekit-work/*/rekit.json`을 찾아 사용한다
   (여러 개면 사용자에게 고르게 한다).
2. `python3 ${CLAUDE_PLUGIN_ROOT}/engine/rekit.py status <ws>` 실행 결과를 한국어로 요약한다
   (실행 상태: running/waiting_human/done/failed, 단계별 상태, 단위 분석 진행률, 질문 현황, 누적 비용).
3. `failed`면 `tail -40 <ws>/.rekit/run.log`로 원인을 요약한다. `waiting_human`이면 `/rekit:answer`를 안내한다.
