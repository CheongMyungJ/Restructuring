#
# S4 controller firmware - PC simulation build
#
#   make              libssdfw.a + libssdsim.a + tools (ssdcli, imgdump)
#   make libssdfw.a   firmware only (HAL 은 링크하는 쪽에서 제공)
#   make asic         ARM 타겟 - 빌드 서버 전용 (arm-none-eabi, asic.ld 필요)
#   make clean
#
#   EXTRA_CFLAGS 로 build option override 가능 (fw_config.h 참고)
#     ex) make EXTRA_CFLAGS="-DCFG_WL_ENABLE=0"
#
# 2016.04 jhkim / 2018.10 jhkim (sim platform 분리)
#

CC       ?= gcc
AR       ?= ar
EXTRA_CFLAGS ?=

CFLAGS   = -std=c99 -O2 -g -Wall -Wextra -Wno-unused-parameter $(EXTRA_CFLAGS)
INCS     = -I. -Iconfig -Ihal -Iutil -Iftl -Icache -Ihost -Ismart -Ithermal
OBJDIR   = build/sim

FW_SRCS  = fw_main.c \
           util/crc32.c util/ring.c util/fw_log.c \
           ftl/ftl_core.c ftl/ftl_alloc.c ftl/ftl_gc.c ftl/ftl_bbm.c \
           ftl/ftl_rr.c ftl/ftl_meta.c ftl/ftl_mount.c ftl/ftl_dbg.c \
           cache/wcache.c \
           host/nvme_io.c host/nvme_admin.c host/nvme_vendor.c \
           smart/smart.c thermal/thermal.c

SIM_SRCS = platform/sim/sim_nand.c platform/sim/sim_env.c

ASIC_SRCS = platform/asic/asic_boot.c platform/asic/asic_nand.c \
            platform/asic/asic_isr.c platform/asic/asic_misc.c

FW_OBJS  = $(patsubst %.c,$(OBJDIR)/%.o,$(FW_SRCS))
SIM_OBJS = $(patsubst %.c,$(OBJDIR)/%.o,$(SIM_SRCS))

TOOLS    = tools/ssdcli tools/imgdump

.PHONY: all clean asic tools

all: libssdfw.a libssdsim.a tools

libssdfw.a: $(FW_OBJS)
	$(AR) rcs $@ $^

libssdsim.a: $(SIM_OBJS)
	$(AR) rcs $@ $^

tools: $(TOOLS)

tools/ssdcli: tools/ssdcli.c libssdfw.a libssdsim.a
	$(CC) $(CFLAGS) $(INCS) -Iplatform/sim $< libssdfw.a libssdsim.a -o $@

tools/imgdump: tools/imgdump.c libssdfw.a libssdsim.a
	$(CC) $(CFLAGS) $(INCS) -Iplatform/sim $< libssdfw.a libssdsim.a -o $@

$(OBJDIR)/%.o: %.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(INCS) -Iplatform/sim -c $< -o $@

asic:
	@echo "asic target: build server only (arm-none-eabi-gcc, platform/asic/asic.ld)"
	@echo "  sources: $(FW_SRCS) $(ASIC_SRCS)"
	@false

clean:
	rm -rf build libssdfw.a libssdsim.a $(TOOLS)
