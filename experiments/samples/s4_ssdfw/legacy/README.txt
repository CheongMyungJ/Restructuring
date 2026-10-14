S4 Controller Firmware (SRK-C400)                     last update 2019.06
=====================================================================

디렉토리
  fw_api.h          host 쪽 API (fw_init / fw_submit / fw_shutdown / fw_tick)
  config/           빌드 설정 (fw_config.h), NAND profile (nand_profile.h)
  hal/              HAL 인터페이스 (NAND, timer, temperature)
  platform/asic/    C400 실제 컨트롤러용 HAL (빌드 서버에서만 빌드)
  platform/sim/     PC 시뮬레이션 HAL (NAND 모델, image save/load, power cut)
  host/             NVMe admin / IO / vendor command
  cache/            DRAM write cache
  ftl/              mapping, GC, WL, bad block, read retry, metadata, mount
  smart/            SMART / health log
  thermal/          thermal throttling
  util/             crc32, ring buffer, log
  tools/            ssdcli (sim 테스트 CLI), imgdump (NAND image dump)

PC sim 빌드
  $ make                 -> libssdfw.a libssdsim.a tools/ssdcli tools/imgdump
  $ make libssdfw.a      -> FW 만 (HAL 미포함)
  $ ./tools/ssdcli script.txt      (명령어는 tools/ssdcli.c 상단 참고)

  build option 은 config/fw_config.h 의 CFG_xxx 참고 (EXTRA_CFLAGS 로 override)

주의
  - on-NAND format (ftl/meta_format.h) 변경 금지. 필드 드라이브 호환.
  - asic 빌드는 arm-none-eabi 툴체인 + 링커 스크립트 필요 (빌드 서버).
  - 자세한 내용은 설계서 (SSD_FW_아키텍처_설계서) 참고.
