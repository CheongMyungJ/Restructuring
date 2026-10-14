# experiments/ — rekit의 형태·데이터 형식을 결정한 실험

결과 요약과 결론: [`REPORT.md`](REPORT.md) · 원자료 표: [`results/exp_raw.md`](results/exp_raw.md)

## 구성
| 경로 | 내용 |
|---|---|
| `lib/claude_run.py` | `claude -p` 실행 래퍼: stream-json 전체 기록, 비용·시간 집계, **작업폴더 밖 경로 접근 감사**(정보 누출 검사) |
| `lib/reports.py` | 샘플별 숨김 하네스 보고서를 하나의 형식으로 정규화 |
| `exp1.py` | 데이터 생성(`gen`)과 변형별 재개발(`redev`) → 숨김 테스트 채점 드라이버 |
| `qa_eval.py` | (실행 불가 펌웨어용) 데이터만 보는 답변자 + 별도 채점자로 재구현자 시험 채점 |
| `kit_coverage.py` | 데이터가 소스 파일·함수를 얼마나 언급하는지 결정적 측정 |
| `aggregate.py` | 결과 집계(`results/`), S3는 운영지식 의존 체크/코드 도출 가능 체크로 분리 |
| `prompts/` | 비교군 생성 프롬프트(단일 세션 키트 `kitgen_v1`, 서술형 `naivedoc`)와 재개발 과제 프롬프트 |
| `samples/` | 샘플 준비 스크립트와 숨김 테스트(아래) |

## 샘플
| ID | 준비 | 숨김 평가 |
|---|---|---|
| S1 NAND FTL (dhara, ISC) | `samples/prepare_s1.sh <dir>` (클론 → 비식별화 → 레거시 테스트 → 숨김 테스트 89/89 확인) | `samples/s1_nandftl/hidden/run_hidden_tests.py <impl>` |
| S2 Cosmos+ OpenSSD (GPLv3) | `samples/prepare_s2.sh <dir>` | `samples/s2_cosmos/hidden/qa.json` + `qa_eval.py` |
| S3 Spring 배치 (합성, 본 저장소 소유) | `samples/s3_tlog/` 그대로 사용 | `samples/s3_tlog/hidden/run_hidden_tests.sh <impl>` (H2 TCP 서버, 145 checks) |
| S4 SSD 펌웨어 (합성, 본 저장소 소유) | `samples/s4_ssdfw/` 그대로 사용 | `samples/s4_ssdfw/hidden/run_hidden_tests.py <impl>` (178 checks) |

`hidden/`은 **재개발 AI에게 절대 주지 않는** 영역입니다(모의 운영 담당자의 지식 `oracle_knowledge.md`, 요청 시 제공
자료 `provided_on_request/`, 기대값, 하네스). 각 `TRAPS.md`에 함정 목록과 영향을 받는 체크가 있습니다.

## 재현 예시
```
export SP=/path/to/work        # 샘플/실험 작업 루트 (exp1.py, aggregate.py가 사용)
bash samples/prepare_s1.sh $SP/samples/s1_nandftl
python3 exp1.py gen s1 naivedoc --model opus            # 서술형 문서 생성
python3 exp1.py gen s1 kitgen_v1 --model opus           # 단일 세션 키트(Form X)
python3 exp1.py redev s1 V0,V1,V3 --reps 1,2            # 변형별 재개발 + 숨김 채점
python3 ../plugins/rekit/engine/rekit.py init $SP/exp/gen/s3/rekit_x --code samples/s3_tlog/legacy \
        --materials samples/s3_tlog/materials --no-intake
python3 ../plugins/rekit/engine/rekit.py run $SP/exp/gen/s3/rekit_x \
        --oracle samples/s3_tlog/hidden/oracle_knowledge.md --oracle-files samples/s3_tlog/hidden/provided_on_request
python3 exp1.py redev s3 V3,V4 --reps 1,2 --kit-method rekit_x
python3 qa_eval.py <kit_dir> samples/s2_cosmos/hidden/qa.json --out qa.json
python3 aggregate.py
```
변형: V0 코드만, V1 서술형 문서, V2 키트(테스트 제외), V3 키트, V4 키트+코드, V5 코드+키트(동작 상세 제외).
