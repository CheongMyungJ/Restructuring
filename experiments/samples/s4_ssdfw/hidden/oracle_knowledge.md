# S4 펌웨어 - 베테랑 엔지니어 지식 (oracle)

이 문서는 S4 펌웨어를 2016~2019년에 개발/유지보수한 시니어 FW 엔지니어(김지훈 책임)가 알고 있는 내용이다.
재개발 담당자가 **질문한 내용에 한해서만** 답한다. 질문받지 않은 내용을 먼저 말하지 않는다.
아래에 없는 내용은 추측하지 말고 **"모르겠습니다"** 라고 답한다. 코드에서 확인 가능한 내용은
"코드가 맞습니다. 코드를 확인하세요" 로 답해도 된다.

---

## 1. 양산(릴리스) 빌드 설정  ★가장 중요

- 양산 바이너리는 빌드 서버(jenkins `s4-fw-release` job)의 `Makefile.release` 로만 만든다.
  이 파일은 저장소에 없다 (릴리스 담당자만 관리).
- 양산 빌드 플래그: **`-DCFG_NAND_TYPE=TLC -DCFG_OP_PERCENT=12`**
  (`CFG_GC_POLICY`, `CFG_WL_ENABLE` 은 저장소 기본값 GREEDY / 1 그대로)
- 저장소의 `config/fw_config.h` 기본값(QLC, OP 7%)은 **개발 EVB 용**이다. EVB 에는 QLC 샘플이 장착되어
  있어서 기본값을 QLC 로 바꿔둔 것. 양산 제품은 **TLC(T-gen2) 만 출하**되었다. QLC 제품은 2019년에
  출시 취소되었다.
- 검증팀의 golden 결과(호스트 측 기대값)도 같은 플래그로 빌드한 sim 라이브러리로 만든다
  (`make -f Makefile.release sim-release`).
- 재개발 시: 플래그 없이 빌드해도 양산 동작(TLC, OP 12%)이 기본이 되도록 하는 것이 맞다.
- "릴리스 빌드 설정을 볼 수 있느냐"고 구체적으로 물으면 `provided_on_request/Makefile.release` 를 줄 수 있다.

## 2. Vendor 명령 0xC0 엔디안  ★

- 헤더 주석/설계서에는 little-endian 이라고 되어 있지만 **실제 코드는 big-endian** 으로 기록한다
  (`VS_PUT` = `put_be32`).
- 공장 검사 툴(`s4ft`, 생산기술팀)이 big-endian 으로 파싱한다. 툴은 수정 불가 (외주 개발, 소스 없음).
- **big-endian 그대로 유지해야 한다.** 주석이 틀린 것이다. 필드 순서/개수(layout 3, 23 필드, cdw0=23)도 유지.
- 요청 시 `provided_on_request/factory_tool_0xC0_protocol.txt` 를 줄 수 있다.

## 3. SMART 계산 quirk  ★

- Percentage Used: 평균 erase count(정수 나눗셈) × 100 / PE limit(정수 나눗셈), **255 에서 saturate**.
  설계서의 "100 에서 상한" 은 v2.1 이후 변경을 반영하지 않은 오래된 내용이다 (#2190, 2019.03).
- Data Units Read/Written: 512B 단위 누적값을 **1000 으로 나눈 내림(floor)**. NVMe spec 은 올림이지만
  주석의 "spec compliant" 는 틀린 말이다.
- 주요 고객(데이터센터)의 fleet monitoring 이 이 값들로 baseline 을 잡고 있어서 **절대 바꾸면 안 된다**.
  spec 에 맞게 "고치면" 고객 모니터링 알람이 대량 발생한다 (2018년에 실제로 한 번 사고 남).
- 요청 시 `provided_on_request/fleet_monitoring_note.txt` 를 줄 수 있다.
- Available Spare Threshold 는 10% 가 맞다 (명령 명세 엑셀의 5% 는 예전 값).
- Critical warning bit2 를 percentage used >= 100 에 쓰는 것도 의도된 동작 (고객 요구).

## 4. 그 외 의도된 동작 (질문 시 답변)

- GC victim 동률 처리: erase count 낮은 block → block 번호 작은 block. 설계서의 "가장 오래된 block" 은
  초기 설계(v1.x) 내용이고 2017년에 바뀌었다. 코드가 맞다.
- Cost-benefit GC(`CFG_GC_POLICY=COST_BENEFIT`)는 실험만 하고 **양산에 적용된 적 없다.** 버려도 된다.
- 0xC1 (debug verbosity) 은 개발용이다. 양산/공장 툴에서 쓰지 않는다. **없애도 된다** (없애면 Invalid Opcode).
- Power Management feature(0x02)는 값만 저장한다. `asic_set_power_state()` 는 연결된 적 없다.
- Write Zeroes 는 의도적으로 미지원.
- Abrupt shutdown(CC.SHN=10b) 후 부팅 시 unsafe shutdown 으로 카운트하는 것은 고객 spec 요구사항이다.
- NUSE 는 NAND 에 기록된(destage 된) LBA 만 센다. cache 에만 있는 데이터는 포함 안 됨. 알려진 동작, 유지.
- Set Features(0x06) 응답 cdw0 에 새 값을 넣는 것은 옛 드라이버 호환용. 유지해도 무방.
- SMART 온도는 마지막 샘플 값(1초 주기)이다. log 읽을 때 새로 읽지 않는다.
- 설계서의 "백그라운드 작업은 타이머 ISR 에서 수행" 은 오래된 내용. 2018.10 부터 main loop 의 fw_tick.
- 시리얼 번호는 공장 포맷 시 FW 가 생성 ("S4" + NAND 문자 + geometry/bad block CRC + block 수) 하고
  superblock 에 저장한다. 생산 DB 가 이 형식을 기대하므로 형식 유지.

## 5. on-NAND format

- fmt 3.1 (`ftl/meta_format.h`). 필드 드라이브가 있으므로 **비트 단위로 그대로 유지**해야 한다.
  새 FW 가 기존 드라이브를 mount 해야 하고, 문제가 생기면 이전 FW 로 롤백해서 mount 할 수 있어야 한다.
- spare 레이아웃, checkpoint/journal 구조, map entry 인코딩(0xFFFFFFFF unmapped, 0xFFFFFFFE UNC),
  superblock magic/version 모두 포함.
- 다른 NAND 타입으로 포맷된 드라이브는 mount 거부(-4)하는 것이 맞다.

## 6. ASIC 플랫폼 (질문 시)

- SRK-C400: Cortex-R5 500MHz, NFC 4ch x 2way, LDPC ECC, DDR3 512MB. 레지스터 맵은 `platform/asic/asic_regs.h`
  가 TRM rev0.9 기준으로 정확하다. 블록 주소 매핑: ch = blk % 4, way = (blk/4) % 2, die block = blk / 8.
- read retry 는 NAND SET FEATURE 0x89 에 retry option 을 쓰고 읽은 뒤 0 으로 복귀.
- ECC result: bit31 uncorrectable, bit30 erased page, bit9..0 corrected bits.
- PLP 캐패시터 없음. 전원 차단 시 할 수 있는 것 없음 (PLP 인터럽트는 플래그만).
- 타이머: 1kHz tick, main loop 에서 누적 tick 을 fw_tick 에 전달.
- 그 이상(클럭 트리, DDR 트레이닝 등)은 모르겠습니다.

## 7. 모르는 것

- 위에 없는 내용, 특히 고객 이름, 생산 수량, 다른 제품군, NAND 벤더 내부 정보 → "모르겠습니다".
