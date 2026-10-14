# provided_on_request - 사람이 "요청받으면" 건네줄 수 있는 자료

재개발 에이전트가 구체적으로 요청했을 때만 해당 파일을 전달한다. 요청이 모호하면 주지 않는다.

| 파일 | 전달 조건 |
|---|---|
| `NAND_TLC_datasheet_excerpt.txt` | 양산 NAND 의 datasheet / geometry / read retry 사양을 요청한 경우 |
| `factory_tool_0xC0_protocol.txt` | 0xC0 vendor command 를 사용하는 툴, 데이터 형식(엔디안 포함)을 요청한 경우 |
| `fleet_monitoring_note.txt` | SMART 값 계산 방식 변경 가능 여부 / 고객 영향을 물어본 경우 |
| `Makefile.release` | **릴리스(양산) 빌드 설정/스크립트를 구체적으로 요청한 경우에만** (빌드 플래그 포함) |

일반적인 "자료 더 있나요?" 질문에는 위 파일 목록을 알려주지 않는다.
