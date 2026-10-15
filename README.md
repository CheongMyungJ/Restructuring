# Restructuring — rekit: 레거시 코드 → AI 재개발 키트 생성기

**rekit**은 레거시 코드와 각종 자료(설계서·인터페이스 정의서·PDF·엑셀·워드·HWP 등)를 입력받아, AI가 그 시스템을
**새 기술 스택으로 재개발할 수 있게 하는 데이터("재개발 키트")** 를 만들어 주는 도구입니다.
코드만으로는 알 수 없는 것(운영 설정 값, 의도된 특이동작, 문서-코드 불일치, 누락 자료 등)은 **사람에게 질문하거나
자료를 요청**하고, 답을 키트에 반영하면서 끝까지 완료합니다.

- 실행 환경: **Claude Code**(`claude` CLI, 로그인 상태) + Python 3.9+ (외부 패키지 불필요. 문서 변환 패키지가 있으면 활용)
- 대상: 언어·프레임워크 무관(범용). **SSD/임베디드 펌웨어(C/C++)**, **Java/Spring 데이터 처리·배치**는 정밀 체크리스트 내장
- 산출물: 한국어 명세(식별자·포맷·SQL·메시지는 원문 그대로) + 레거시를 실제 실행해 얻은 골든 테스트 + 구현 계획

> 도구의 형태와 데이터 형식은 **자체 실험으로 결정**했습니다(실제·합성 레거시 4종, AI 재개발 수십 회를 숨김 테스트로 채점,
> 실제 SSD 펌웨어 재구현자 시험 70문항). 요약은 아래 §8, 상세는 [`experiments/REPORT.md`](experiments/REPORT.md).

---

## 1. 설치

**Claude Code 플러그인 (권장)** — Claude Code 안에서:
```
/plugin marketplace add CheongMyungJ/Restructuring
/plugin install rekit@restructuring
```
(Claude Code 2.1.275+ 는 한 줄: `/plugin install rekit --marketplace CheongMyungJ/Restructuring`)

**터미널 도구로만** 쓰려면:
```
git clone https://github.com/CheongMyungJ/Restructuring
python3 Restructuring/plugins/rekit/engine/rekit.py doctor     # 필수/선택 도구 점검
```

## 2. 사용법 — Claude Code에서 대화로
```
/rekit:start ./legacy-src ./docs
```
1. **환경 점검** → **사전 인터뷰**: 재개발 목적, 목표 스택, 반드시 유지할 호환성, 제외 범위, 실행 환경,
   **운영에서만 적용되는 설정 값/파일**(JVM 옵션, 릴리스 빌드 플래그 등 — 실험상 결과를 가장 크게 좌우), 답변자.
2. **규모·비용 안내** 후 품질 프리셋(`max`/`balanced`/`economy`)과 비용 상한을 정하고 시작합니다.
3. 엔진이 **백그라운드**로 분석합니다. 다른 일을 해도 되고 `/rekit:status`로 확인합니다.
4. 사람의 확인이 필요하면 **선택지 형태의 질문**을 보여 줍니다(`/rekit:answer`). 자료 요청이면 파일 경로를 받습니다.
   다른 담당자에게 물어야 하면 **질문지(Markdown)로 내보내고** 작성본을 다시 가져올 수 있습니다.
5. 완료되면 키트 위치·소스 커버리지·남은 질문(적용된 가정)·비용을 보고합니다.

## 3. 사용법 — 터미널에서
```
RK="python3 plugins/rekit/engine/rekit.py"
$RK init  work/mysys --code ./legacy-src --materials ./docs --preset balanced --budget 100
$RK run   work/mysys --bg          # 백그라운드 실행 (로그: work/mysys/.rekit/run.log)
$RK wait  work/mysys               # 멈출 때까지 대기 → done / waiting_human / failed / paused
$RK answer work/mysys              # 대화형 답변 (번호·자유입력, s=보류, f <경로>=자료로 답변)
$RK run   work/mysys --bg          # 이어서 진행 (끝난 단계는 건너뜀)
$RK status work/mysys
```
- 질문지로 받기: `$RK questions work/mysys --export 질문지.md` → 담당자 작성(답변: 줄, 번호/자유입력/파일 경로/모름) →
  `$RK answer work/mysys --import 질문지.md`
- 개별 답변: `$RK answer work/mysys --set Q-XXX-01 "답" [--file 자료경로]`, 보류: `--defer Q-XXX-01`
- 자료 추가: `$RK add-material work/mysys ./추가자료.pdf` · 소스 커버리지: `$RK coverage work/mysys`
- 종료코드: 0 완료/정상, **10 사람 확인 필요**, 1 오류(그대로 다시 실행하면 이어서 진행)

## 4. 키트(산출물) 구조
```
kit/
  README.md            구현 AI의 진입점: 읽는 순서, ID/태그 규칙, 유지 필수 계약 목록, 테스트·계획 사용법
  00_overview.md       목적·범위·시스템 경계·외부 주체·핵심 흐름(FL-*)
  01_glossary.md       용어 ↔ 코드 식별자 ↔ 의미
  02_architecture.md   구성요소, 실행 모델(태스크/ISR/잡), 설정·빌드 변형(운영값 포함), 레거시→신규 매핑, 제외 코드
  03_interfaces/       외부 계약(IF-*): API/ABI, 파일·전문 포맷(바이트 단위), DB·SQL 의미, 명령/프로토콜, 운영 인터페이스
  04_data/             영속/핵심 데이터 구조(DM-*): 온미디어(NAND) 포맷, 레이아웃, 불변식
  05_behavior/         모듈별 동작: 규칙 BR-*, 알고리즘 ALG-*(레거시에 충실한 의사코드), 상태기계 SM-*, 오류 ERR-*
  06_nfr.md            성능·메모리·타이밍·신뢰성·운영 요구
  07_tests/            테스트 벡터(TV-*) + 레거시를 실제 실행해 얻은 골든(특성화) 테스트와 실행 스크립트
  08_decisions.md      사람이 확인한 사실·결정(DEC-*): 운영 설정, 유지할 특이동작, 폐기 대상
  09_open_questions.md 미해결 질문과 현재 적용한 가정(사람이 검토할 위험 목록)
  10_plan.md           구현 태스크(T-*) 순서, 태스크별 로드할 명세(컨텍스트 팩), 완료 기준
  trace.json           ID → 키트 파일·레거시 소스 위치·신뢰도
```
모든 항목에 출처 `(src: 파일:줄)`, 신뢰도(`[코드확인]` `[실행확인]` `[문서]` `[사람확인]` `[추정]`),
`계약(유지 필수)` / `구현상세(변경 가능)` 구분이 붙습니다.

## 5. 동작 방식
```
inventory → survey → units(병렬) → synthesize → gate1(사람) → characterize → [review/fix] → gate2(사람) → finalize
```
| 단계 | 내용 |
|---|---|
| inventory | 파일 분류·LOC·토큰·심볼 수집(결정적), 자료 텍스트 변환(PDF/DOCX/XLSX/PPTX/HWPX, HWP·DOC 등은 변환기 있으면) |
| survey | 시스템 경계·외부 계약 파악, **모듈 단위 분할**(작을수록 정밀 — 실측), 초기 질문 |
| units | 단위별 독립 AI 세션이 코드를 **한 줄도 빠짐없이** 읽고 규칙·알고리즘·계약·테스트 벡터·질문 작성(+커버리지 표) |
| synthesize | 인터페이스·데이터·개요·흐름 통합, 질문 중복 제거·우선순위화 (대규모는 서브시스템별 계층 통합) |
| gate | 사람에게 질문(blocking/important) → 답을 키트에 반영(DEC-*), 후속 질문 |
| characterize | 레거시를 (시뮬레이터·스텁·임베디드 DB 등으로) 실제 빌드·실행해 **골든 테스트** 생성, 키트 교정 |
| review/fix (`max`만) | **코드 없이 키트만 가진 구현자 AI**가 빠짐·모호함을 찾고, 코드를 보는 AI가 메우거나 질문으로 전환 |
| finalize | 소스 커버리지 점검, 구현 계획·README·추적표 완성 |

각 AI 단계는 새 `claude -p` 세션이며, 상태는 작업폴더 `.rekit/`에 저장되어 **중단 후 재개**할 수 있습니다.

## 6. 키트로 재개발하기
새 프로젝트 저장소에 `kit/`를 복사하고(**레거시 코드도 `legacy/`로 함께 두는 것을 권장**) Claude Code에서
```
/rekit:implement kit
```
또는 "kit/README.md를 읽고 10_plan.md 순서대로 구현해줘". 구현 AI는 태스크별 컨텍스트 팩만 읽고, 테스트 벡터와
골든 테스트로 스스로 검증하며 진행합니다.

## 7. 프리셋·비용
| 프리셋 | 모델 | 분석 단위 | 단계 | 용도 |
|---|---|---|---|---|
| `max` | Opus | 작게(≈10K 토큰) | 특성화 + 검토/보완 | 정밀도 최우선 (비용 최대) |
| `balanced` (기본) | Opus | 중간(≈20K 토큰) | 특성화 | 일반 권장 |
| `economy` | Sonnet | 크게(≈40K 토큰) | 특성화 | 대형 코드베이스 1차 분석, 비용 절감 |

검토/보완(review/fix: 코드 없이 키트만 가진 AI가 빈틈을 찾고 메움)은 실측에서 통합 직후 대비 정답률을 올리지 못하고
(95.1% → 94.1%) 비용만 약 2.4배가 되어 `max`에서만 켭니다. 레거시를 실제 실행하는 특성화(골든 테스트)는 모든 프리셋에서 켭니다.
비용은 코드 규모·단위 수에 비례합니다. 실측(Opus, 사람 질의응답 포함 전체 파이프라인):

| 레거시 | 코드 토큰 | 전체(검토/보완 포함) | 검토/보완 제외(≈`balanced`) |
|---|---|---|---|
| Java/Spring 배치 3.2K LOC | 37K | $35~71 | $25~44 |
| SSD 펌웨어(합성) 4.5K LOC | 42K | $109~137 | $57~81 |
| SSD 펌웨어(Cosmos+) 7.4K LOC | 81K | $107 | $61 |

대략 코드 1만 토큰당 `balanced` $7~20, `max` $15~35, `economy`(Sonnet) 그 1/5 수준. 레거시 실행(특성화)이 길어지는
펌웨어가 더 비쌉니다. `--budget`으로 상한을 두면 도달 시 멈추고 재개할 수 있습니다.

## 8. 실험으로 확인한 사실 (요약)
- 코드에 **들어 있는** 동작은 강한 AI가 코드나 문서만으로도 거의 완벽히 재현한다. 실패는 거의 전부 **코드 밖 지식**
  (운영 JVM 옵션, 릴리스 빌드 플래그 등)에서 났다 → 키트의 핵심 가치는 그 지식을 사람에게서 확보해 명시하는 것.
- 실제 SSD 펌웨어 재구현자 시험: **구조화 키트(파이프라인) 95%** > 단일 세션 키트 93% > 서술형 문서 88% > 원본 코드 87%
  (오답·환각 0~1). 잘 만든 키트는 원본 코드보다 정확하고 싸게 답하게 한다.
- 분석 단위를 작게 나눌수록 정밀(같은 모델 95% vs 91%). 키트/문서 기반 재개발은 코드 기반보다 비용·시간이 약 절반.
- 상세 수치·방법·한계: [`experiments/REPORT.md`](experiments/REPORT.md)

## 9. 저장소 구성
```
.claude-plugin/marketplace.json   플러그인 마켓플레이스
plugins/rekit/                    플러그인: skills/(start, status, answer, implement), engine/(rekit.py, 테스트)
experiments/                      실험 코드·프롬프트·샘플(합성 S3/S4 전체, S1/S2 준비 스크립트)·결과·보고서
```
엔진 단위 테스트(오프라인): `cd plugins/rekit/engine && python3 -m unittest discover -s tests`
