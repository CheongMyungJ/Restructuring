/*
 * nvme_io.c - I/O command set (FLUSH / WRITE / READ / DSM)
 *
 * 검사 순서: nsid -> MDTS -> LBA range
 * host read/write command 카운터는 검사 통과한 command 만 센다.
 * data unit 카운터는 성공한 command 만.
 *
 *  2016.04 jhkim   initial
 *  2018.02 hwchoi  write cache 연동, FUA
 *  2018.11 mjlee   thermal throttle (cache limit / write-through)
 */
#include "nvme_int.h"
#include "fw_config.h"
#include "ftl.h"
#include "wcache.h"
#include "thermal.h"
#include "bitops.h"
#include "fw_log.h"

static uint16_t io_check(const nvme_cmd_t *cmd, uint32_t *pn)
{
    uint64_t n = (uint64_t)cmd->nlb + 1;

    if (cmd->nsid != 1)
        return ST_INV_NS;
    if (n > MDTS_LBAS)
        return ST_INV_FIELD;
    if (cmd->slba >= g_ftl.capacity || cmd->slba + n > g_ftl.capacity)
        return ST_LBA_RANGE;
    *pn = (uint32_t)n;
    return ST_OK;
}

static uint16_t io_read(const nvme_cmd_t *cmd, uint8_t *buf)
{
    uint32_t n, i, lba;
    uint16_t st;

    st = io_check(cmd, &n);
    if (st != ST_OK)
        return st;
    if (buf == NULL)
        return ST_XFER_ERR;
    g_cnt.host_read_cmds++;

    for (i = 0; i < n; i++) {
        lba = (uint32_t)cmd->slba + i;
        if (WC_Read(lba, buf + (size_t)i * LBA_SIZE))
            continue;
        if (ftl_read_lba(lba, buf + (size_t)i * LBA_SIZE) != FTL_OK) {
            g_cnt.media_errors++;
            return ST_UNRECOVERED;
        }
    }
    g_cnt.du_read_raw += (uint64_t)n * SECTORS_PER_LBA;
    return ST_OK;
}

static uint16_t io_write(const nvme_cmd_t *cmd, const uint8_t *buf)
{
    uint32_t n, i, lba, limit, lvl;
    uint16_t st;
    int fua, wt, rc;

    st = io_check(cmd, &n);
    if (st != ST_OK)
        return st;
    if (buf == NULL)
        return ST_XFER_ERR;
    g_cnt.host_write_cmds++;

    lvl   = thermal_level();
    fua   = (cmd->cdw12 >> 30) & 1;
    wt    = fua || !g_feat.vwc || (lvl >= 3);
    limit = (lvl >= 2) ? (CACHE_ENTRIES / 2) : CACHE_ENTRIES;

    for (i = 0; i < n; i++) {
        lba = (uint32_t)cmd->slba + i;
        if (wt) {
            WC_Invalidate(lba);
            rc = ftl_write_lba(STREAM_HOST, lba, buf + (size_t)i * LBA_SIZE);
        } else {
            rc = WC_Write(lba, buf + (size_t)i * LBA_SIZE, limit);
        }
        if (rc != FTL_OK) {
            st = ST_WRITE_FAULT;
            break;
        }
    }
    if (wt) {
        if (ftl_flush_stream(STREAM_HOST) != FTL_OK)
            st = ST_WRITE_FAULT;
        jrnl_commit(0, 0);
    }
    if (st == ST_OK) {
        g_cnt.du_written_raw += (uint64_t)n * SECTORS_PER_LBA;
        g_ftl.writes_since_ckpt += n;
    }
    return st;
}

static uint16_t io_flush(const nvme_cmd_t *cmd)
{
    int rc;

    if (cmd->nsid != 1 && cmd->nsid != NSID_ALL)
        return ST_INV_NS;
    rc = WC_FlushAll();
    jrnl_commit(0, 0);
    return (rc == FTL_OK) ? ST_OK : ST_WRITE_FAULT;
}

/* Dataset Management - deallocate(AD) 만 지원, 나머지 attribute 는 무시 */
static uint16_t io_dsm(const nvme_cmd_t *cmd, const uint8_t *buf)
{
    uint32_t nr, r, len, lba;
    uint64_t slba;
    const uint8_t *p;

    if (cmd->nsid != 1)
        return ST_INV_NS;
    if (!(cmd->cdw11 & BIT(2)))
        return ST_OK;
    if (buf == NULL)
        return ST_XFER_ERR;
    nr = (cmd->cdw10 & 0xFF) + 1;

    for (r = 0; r < nr; r++) {
        p = buf + r * 16;
        len  = get_le32(p + 4);
        slba = (uint64_t)get_le32(p + 8) | ((uint64_t)get_le32(p + 12) << 32);
        if (len == 0)
            continue;
        if (slba >= g_ftl.capacity || slba + len > g_ftl.capacity)
            return ST_LBA_RANGE;
    }
    for (r = 0; r < nr; r++) {
        p = buf + r * 16;
        len  = get_le32(p + 4);
        slba = (uint64_t)get_le32(p + 8);
        for (lba = (uint32_t)slba; lba < (uint32_t)slba + len; lba++) {
            WC_Invalidate(lba);
            ftl_trim_lba(lba);
        }
    }
    return ST_OK;
}

uint16_t nvme_io_cmd(const nvme_cmd_t *cmd, void *buf, uint32_t *cdw0)
{
    (void)cdw0;
    switch (cmd->opcode) {
    case NVME_IO_FLUSH:
        return io_flush(cmd);
    case NVME_IO_WRITE:
        return io_write(cmd, (const uint8_t *)buf);
    case NVME_IO_READ:
        return io_read(cmd, (uint8_t *)buf);
    case NVME_IO_DSM:
        return io_dsm(cmd, (const uint8_t *)buf);
#if 0
    case 0x08:  /* write zeroes - S3 에서 지원, S4 미지원 (2017.02 삭제) */
        return io_write_zeroes(cmd);
#endif
    default:
        LOGW("io", "invalid io opcode %02x", cmd->opcode);
        return ST_INV_OPC;
    }
}
