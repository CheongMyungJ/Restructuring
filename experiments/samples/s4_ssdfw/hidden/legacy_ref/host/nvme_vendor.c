/*
 * nvme_vendor.c - vendor specific admin commands
 *
 *   0xC0  DUMP INTERNAL COUNTERS
 *         data: 512 bytes, u32 fields, little-endian (host byte order)
 *           0x00 signature 'S4DC'      0x04 layout version
 *           0x08 GC count              0x0C WL count
 *           0x10 bad block total       0x14 grown bad blocks
 *           0x18 read retry count      0x1C refresh count
 *           0x20 refresh (read retry)  0x24 refresh (read disturb)
 *           0x28 free blocks           0x2C min EC
 *           0x30 max EC                0x34 avg EC
 *           0x38 program fail          0x3C erase fail
 *           0x40 thermal level         0x44 throttle events
 *           0x48 cache dirty entries   0x4C checkpoint count
 *           0x50 NAND data page prog   0x54 format count
 *           0x58 debug level
 *         cdw0 = number of valid fields
 *   0xC1  SET DEBUG VERBOSITY  cdw10 = level (0..4), cdw0 = previous level
 *
 *  2017.02 hwchoi  initial
 *  2018.04 dykang  bad block / fail 카운터 추가 (layout 2)
 *  2018.11 mjlee   thermal 필드 추가 (layout 3)
 */
#include "nvme_int.h"
#include "fw_config.h"
#include "ftl.h"
#include "wcache.h"
#include "thermal.h"
#include "bitops.h"
#include "fw_log.h"

#define VS_SIGNATURE        0x53344443u     /* 'S4DC' */
#define VS_LAYOUT_VER       3
#define VS_NUM_FIELDS       23

/* host byte order 로 기록 */
#define VS_PUT(buf, off, v)     put_be32((buf) + (off), (uint32_t)(v))

static uint16_t vs_dump_counters(uint8_t *buf, uint32_t *cdw0)
{
    uint32_t mn, mx, avg;

    if (buf == NULL)
        return ST_XFER_ERR;
    ftl_ec_stats(&mn, &mx, &avg);
    memset(buf, 0, VS_DUMP_SIZE);

    VS_PUT(buf, 0x00, VS_SIGNATURE);
    VS_PUT(buf, 0x04, VS_LAYOUT_VER);
    VS_PUT(buf, 0x08, g_cnt.gc_count);
    VS_PUT(buf, 0x0C, g_cnt.wl_count);
    VS_PUT(buf, 0x10, ftl_bad_total());
    VS_PUT(buf, 0x14, g_cnt.grown_bad_count);
    VS_PUT(buf, 0x18, g_cnt.rr_count);
    VS_PUT(buf, 0x1C, g_cnt.refresh_count);
    VS_PUT(buf, 0x20, g_cnt.rr_refresh_count);
    VS_PUT(buf, 0x24, g_cnt.rd_refresh_count);
    VS_PUT(buf, 0x28, g_ftl.free_cnt);
    VS_PUT(buf, 0x2C, mn);
    VS_PUT(buf, 0x30, mx);
    VS_PUT(buf, 0x34, avg);
    VS_PUT(buf, 0x38, g_cnt.prog_fail_count);
    VS_PUT(buf, 0x3C, g_cnt.erase_fail_count);
    VS_PUT(buf, 0x40, thermal_level());
    VS_PUT(buf, 0x44, g_cnt.throttle_events);
    VS_PUT(buf, 0x48, WC_DirtyCount());
    VS_PUT(buf, 0x4C, g_cnt.ckpt_count);
    VS_PUT(buf, 0x50, (uint32_t)g_cnt.nand_data_programs);
    VS_PUT(buf, 0x54, g_cnt.format_count);
    VS_PUT(buf, 0x58, g_fw_dbg_level);

    *cdw0 = VS_NUM_FIELDS;
    return ST_OK;
}

static uint16_t vs_set_debug(const nvme_cmd_t *cmd, uint32_t *cdw0)
{
    uint32_t lvl = cmd->cdw10;

    if (lvl > FW_DBG_MAX)
        return ST_INV_FIELD;
    *cdw0 = g_fw_dbg_level;
    g_fw_dbg_level = lvl;
    return ST_OK;
}

uint16_t nvme_vendor_cmd(const nvme_cmd_t *cmd, void *buf, uint32_t *cdw0)
{
    switch (cmd->opcode) {
    case NVME_ADM_VS_DUMP_COUNTERS:
        return vs_dump_counters((uint8_t *)buf, cdw0);
    case NVME_ADM_VS_SET_DEBUG:
        return vs_set_debug(cmd, cdw0);
    default:
        return ST_INV_OPC;
    }
}
