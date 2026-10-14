# Restructuring — rekit: 레거시 코드 → AI 재개발 키트 생성기

**rekit**은 레거시 코드와 각종 자료(설계서·인터페이스 정의서·PDF·엑셀·HWP 등)를 입력받아, AI가 그 시스템을
**새 기술 스택으로 재개발할 수 있도록 하는 데이터("재개발 키트")** 를 만들어 주는 도구입니다.
분석 중 코드만으로는 알 수 없는 것(운영 설정, 의도된 특이동작, 문서-코드 불일치, 누락 자료 등)은
**사람에게 질문하거나 자료를 요청**하고, 답을 키트에 반영하면서 끝까지 완료합니다.

- 실행 환경: Claude Code(`claude` CLI) + Python 3.9+ (외부 패키지 불필요, 문서 변환용 패키지는 있으면 사용)
- 대상: 언어·프레임워크 무관(범용). SSD/임베디드 펌웨어(C/C++), Java/Spring 데이터 처리·배치에 대한 정밀 체크리스트 내장
- 산출물 언어: 한국어(식별자·포맷·SQL·메시지 등은 원문 유지)

> 이 형태와 데이터 형식은 자체 실험(실제·합성 레거시 4종, 수십 회의 AI 재개발 및 숨김 테스트 채점)으로 결정했습니다.
> 실험 설계·결과: [`experiments/REPORT.md`](experiments/REPORT.md)

---

## 1. 설치

### Claude Code 플러그인으로 (권장)
```
/plugin marketplace add CheongMyungJ/Restructuring
/plugin install rekit@restructuring
```
(Claude Code 2.1.275+ 에서는 한 줄로: `/plugin install rekit --marketplace CheongMyungJ/Restructuring`)

### 터미널 도구로 (플러그인 없이)
```
git clone https://github.com/CheongMyungJ/Restructuring
python3 Restructuring/plugins/rekit/engine/rekit.py -h
```

## 2. 사용법

### Claude Code에서 (대화형)
```
/rekit:start ./legacy-src ./docs
```
1. 사전 인터뷰(재개발 목적, 목표 스택, 반드시 유지할 호환성, 제외 범위, 실행 환경, 답변자)를 선택지로 묻습니다.
2. 규모(파일/LOC/토큰)와 예상 비용·시간을 보여주고 진행 여부를 확인합니다.
3. 엔진이 백그라운드로 분석합니다(`/rekit:status`로 진행 확인).
4. 사람이 답해야 할 질문이 생기면 선택지 형태로 묻습니다(`/rekit:answer`). 자료 요청이면 파일 경로를 받습니다.
   다른 담당자에게 물어야 하면 질문지(Markdown)로 내보내고 나중에 가져올 수 있습니다.
5. 완료되면 키트 위치·커버리지·남은 질문·비용을 보고합니다.

### 터미널에서
```
RK="python3 plugins/rekit/engine/rekit.py"
$RK init  work/mysys --code ./legacy-src --materials ./docs     # 사전 질문(Enter로 건너뛰기 가능)
$RK run   work/mysys            # 질문이 필요하면 종료코드 10으로 멈춤
$RK answer work/mysys           # 터미널에서 대화형 답변 (번호/자유입력, s=보류, f <경로>=자료 첨부)
$RK run   work/mysys            # 이어서 진행 (완료된 단계는 건너뜀)
$RK status work/mysys
```
- 백그라운드 실행: `$RK run work/mysys --bg` (로그 `work/mysys/.rekit/run.log`)
- 담당자에게 질문지 보내기: `$RK questions work/mysys --export 질문지.md` → 작성 후 `$RK answer work/mysys --import 질문지.md`
- 자료 추가: `$RK add-material work/mysys ./추가자료.pdf`
- 비용 상한/모델: `work/mysys/rekit.json`의 `max_cost_usd`, `models`(단계별 `opus`/`sonnet`), `parallel`

## 3. 키트(산출물) 구조
```
kit/
  README.md            구현 AI를 위한 진입점: 읽는 순서, ID/태그 규칙, 유지 필수 계약 목록, 테스트·계획 사용법
  00_overview.md       목적·범위·시스템 경계·외부 주체·핵심 흐름(FL-*)
  01_glossary.md       용어 ↔ 코드 식별자 ↔ 의미
  02_architecture.md   구성요소, 실행 모델(태스크/ISR/잡), 설정·빌드 변형, 레거시→신규 구조 매핑, 제외 코드
  03_interfaces/       외부 계약(IF-*): API/ABI, 파일·전문 포맷(바이트 단위), DB·SQL 의미, 프로토콜·명령, 운영 인터페이스
  04_data/             영속/핵심 데이터 구조(DM-*): 온미디어 포맷, 레이아웃, 불변식
  05_behavior/         모듈별 동작 명세: 규칙 BR-*, 알고리즘 ALG-*(레거시에 충실한 의사코드), 상태기계 SM-*, 오류 ERR-*
  06_nfr.md            성능·메모리·타이밍·신뢰성·운영 요구
  07_tests/            테스트 벡터(TV-*)와 레거시를 실제 실행해 얻은 골든(특성화) 테스트 + 실행 스크립트
  08_decisions.md      사람이 확인한 사실·결정(DEC-*), 보존할 특이동작, 폐기 대상
  09_open_questions.md 미해결 질문과 현재 적용한 가정
  10_plan.md           구현 태스크(T-*) 순서, 태스크별 로드할 명세(컨텍스트 팩), 완료 기준
  trace.json           ID → 키트 파일·레거시 소스 위치·신뢰도
```
모든 항목에는 출처 `(src: 파일:줄)`과 신뢰도 태그(`[코드확인]` `[실행확인]` `[문서]` `[사람확인]` `[추정]`),
그리고 `계약(유지 필수)` / `구현상세(변경 가능)` 구분이 붙습니다.

## 4. 동작 방식
```
inventory ─ survey ─ units(병렬) ─ synthesize ─ gate1(사람) ─ characterize ─ review/fix ─ gate2(사람) ─ finalize
```
| 단계 | 내용 |
|---|---|
| inventory | 파일 분류·LOC·토큰·심볼 수집(결정적), 자료를 텍스트로 변환(PDF/DOCX/XLSX/PPTX/HWPX/HWP*) |
| survey | 시스템 경계·외부 계약 파악, 분석 단위(모듈) 분할, 초기 질문 |
| units | 단위별 별도 AI 세션이 **모든 코드를 한 줄도 빠짐없이** 읽고 규칙·알고리즘·계약·테스트 벡터·질문 작성 |
| synthesize | 인터페이스/데이터/개요/흐름 통합, 질문 중복 제거·우선순위화 (대규모는 서브시스템별 계층 통합) |
| gate | 사람에게 질문 → 답을 키트에 반영(DEC-*), 후속 질문 생성 |
| characterize | 레거시를 (시뮬레이터/스텁/임베디드 DB 등으로) 실제 빌드·실행해 골든 테스트 생성, 키트 교정 |
| review/fix | **코드 없이 키트만 가진 구현자 AI**가 빠짐·모호함을 찾고, 코드를 보는 AI가 메움 |
| finalize | 소스 커버리지 점검, 구현 계획·README·추적표 완성 |

각 AI 단계는 새 `claude -p` 세션으로 실행되며, 모든 상태는 작업폴더 `.rekit/`에 저장되어 중단 후 재개할 수 있습니다.

## 5. 키트로 재개발하기
새 프로젝트 저장소에 `kit/`를 복사하고(가능하면 레거시 코드도 `legacy/`로 함께) Claude Code에서:
```
/rekit:implement kit
```
또는 "kit/README.md를 읽고 10_plan.md 순서대로 구현해줘". 구현 AI는 태스크별 컨텍스트 팩만 읽고,
테스트 벡터와 골든 테스트로 스스로 검증하며 진행합니다.

## 6. 저장소 구성
```
.claude-plugin/marketplace.json   플러그인 마켓플레이스
plugins/rekit/                    플러그인 (skills/, engine/)
experiments/                      실험 코드·프롬프트·결과·보고서
```
