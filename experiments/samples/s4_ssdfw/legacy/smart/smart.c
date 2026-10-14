/*
 * smart.c - SMART / Health log (NVMe 1.3 Figure 94 layout)
 *
 * 카운터 원본은 g_cnt (fw_persist_t) 에 있고 checkpoint / journal 로 persist.
 *
 *  2016.08 hjyoon  initial
 *  2018.09 sypark  persist 영역 이동 (fmt 3.0)
 *  2019.03 hjyoon  percentage used 계산 변경 (#2190)
 */
#include "smart.h"
#include "fw_config.h"
#include "nand_profile.h"
#include "ftl.h"
#include "thermal.h"
#include "bitops.h"

extern uint16_t nvme_feat_temp_thresh(void);

/*
 * percentage used = 평균 erase count * 100 / PE limit
 * spec: 100 초과 가능, 255 에서 saturate
 */
uint8_t smart_percent_used(void)
{
    uint32_t avg, pct;

    ftl_ec_stats(NULL, NULL, &avg);
    pct = avg * 100 / NAND_PE_LIMIT;
    if (pct > 255)
        pct = 255;
    return (uint8_t)pct;
}

uint8_t smart_avail_spare(void)
{
    return (uint8_t)ftl_avail_spare_pct();
}

uint8_t smart_critical_warning(void)
{
    uint8_t cw = 0;

    if (smart_avail_spare() < SPARE_THRESHOLD_PCT)
        cw |= CW_SPARE;
    if (thermal_temp_k() >= nvme_feat_temp_thresh())
        cw |= CW_TEMPERATURE;
    if (smart_percent_used() >= 100)
        cw |= CW_RELIABILITY;       /* 수명 소진 */
    return cw;
}

/* data unit = 1000 x 512B.  NVMe spec 준수 (spec compliant) */
static uint64_t du_conv(uint64_t raw512)
{
    return raw512 / 1000;
}

void smart_build_log(uint8_t *log)
{
    uint16_t tk = thermal_temp_k();

    memset(log, 0, SMART_LOG_SIZE);
    log[0] = smart_critical_warning();
    put_le16(&log[1], tk);
    log[3] = smart_avail_spare();
    log[4] = SPARE_THRESHOLD_PCT;
    log[5] = smart_percent_used();
    log[6] = 0;                                     /* endurance group summary */
    put_le128(&log[32],  du_conv(g_cnt.du_read_raw));
    put_le128(&log[48],  du_conv(g_cnt.du_written_raw));
    put_le128(&log[64],  g_cnt.host_read_cmds);
    put_le128(&log[80],  g_cnt.host_write_cmds);
    put_le128(&log[96],  0);                        /* controller busy time: 미구현 */
    put_le128(&log[112], g_cnt.power_cycles);
    put_le128(&log[128], g_cnt.poweron_ms / 3600000ULL);
    put_le128(&log[144], g_cnt.unsafe_shutdowns);
    put_le128(&log[160], g_cnt.media_errors);
    put_le128(&log[176], g_cnt.err_log_entries);
    /* 192: warning temp time, 196: critical temp time - 미구현 (0) */
    put_le16(&log[200], tk);                        /* temperature sensor 1 */
}
