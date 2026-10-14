/*
 * fw_main.c - firmware entry points (fw_api.h)
 *
 * asic: main() in platform/asic/asic_boot.c 가 fw_init() 후 main loop 에서
 *       SQ doorbell 처리 -> fw_submit(), 1ms timer -> fw_tick()
 * sim : tools/ 또는 test program 이 직접 호출
 *
 *  2016.04 jhkim   initial
 *  2018.10 jhkim   background 작업을 fw_tick() 으로 분리
 */
#include "fw_api.h"
#include "fw_config.h"
#include "ftl.h"
#include "wcache.h"
#include "thermal.h"
#include "smart.h"
#include "host/nvme_int.h"
#include "fw_log.h"

static struct {
    uint8_t  up;
    uint64_t uptime_ms;
    uint64_t last_io_ms;
} g_fw;

int fw_init(void)
{
    int rc;

    memset(&g_fw, 0, sizeof(g_fw));
    g_fw_dbg_level = FW_DBG_DEFAULT;
    ftl_ram_reset();
    WC_Init();
    thermal_reset();
    nvme_feat_reset();

    rc = ftl_mount();
    if (rc != FW_OK) {
        LOGE("main", "mount failed (%d)", rc);
        return rc;
    }
    thermal_poll();
    g_fw.up = 1;
    LOGI("main", "fw %s up: %s, cap %u, free %u, pc %llu, unsafe %llu", FW_REVISION,
         NAND_TYPE_NAME, g_ftl.capacity, g_ftl.free_cnt,
         (unsigned long long)g_cnt.power_cycles, (unsigned long long)g_cnt.unsafe_shutdowns);
    return FW_OK;
}

void fw_submit(const nvme_cmd_t *cmd, void *buf, nvme_cpl_t *cpl)
{
    uint16_t st;
    uint32_t cdw0 = 0;

    memset(cpl, 0, sizeof(*cpl));
    cpl->sqid = cmd->sqid;
    cpl->cid = cmd->cid;
    if (!g_fw.up) {
        cpl->status = ST_INTERNAL;
        return;
    }

    if (cmd->sqid == 0) {
        st = nvme_admin_cmd(cmd, buf, &cdw0);
    } else {
        st = nvme_io_cmd(cmd, buf, &cdw0);
        g_fw.last_io_ms = g_fw.uptime_ms;
    }
    if (st != ST_OK)
        g_cnt.err_log_entries++;

    bbm_service();
    ftl_meta_after_cmd();

    cpl->cdw0 = cdw0;
    cpl->status = st;
}

void fw_tick(uint32_t ms)
{
    uint64_t idle;

    if (!g_fw.up)
        return;
    g_fw.uptime_ms += ms;
    g_cnt.poweron_ms += ms;

    thermal_tick(ms);
    bbm_service();
    refresh_service();

    idle = g_fw.uptime_ms - g_fw.last_io_ms;
    gc_idle_step(idle > 0xFFFFFFFFu ? 0xFFFFFFFFu : (uint32_t)idle, thermal_level());
    ftl_meta_after_cmd();
}

void fw_shutdown(int clean)
{
    if (!g_fw.up)
        return;
    (void)WC_FlushAll();
    bbm_service();
    if (clean) {
        (void)ckpt_write(SPF_CLEAN);
    } else {
        /* abrupt (CC.SHN=10b): data 만 보존, clean mark 없음 */
        jrnl_commit(1, 0);
    }
    g_fw.up = 0;
    LOGI("main", "shutdown (%s)", clean ? "normal" : "abrupt");
}

int fw_debug_check(void)
{
    int err;

    if (!g_fw.up)
        return -1;
    ftl_dump_summary();
    err = ftl_check_consistency();
    LOGE("main", "consistency check: %d error(s)", err);
    return err;
}
