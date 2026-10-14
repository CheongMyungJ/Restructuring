/*
 * nvme_admin.c - admin command set
 *   IDENTIFY (CNS 0/1/2), GET LOG PAGE (SMART), SET/GET FEATURES, FORMAT NVM
 *
 *  2016.04 jhkim   initial
 *  2016.08 hjyoon  SMART log
 *  2017.02 hwchoi  vendor command 분리 (nvme_vendor.c)
 */
#include "nvme_int.h"
#include "fw_config.h"
#include "nand_profile.h"
#include "ftl.h"
#include "wcache.h"
#include "smart.h"
#include "bitops.h"
#include "fw_log.h"

nvme_feat_t g_feat;

void nvme_feat_reset(void)
{
    g_feat.vwc = 1;
    g_feat.ps = 0;
    g_feat.tmpth_k = TEMP_THRESH_DEF_K;
}

uint16_t nvme_feat_temp_thresh(void)
{
    return g_feat.tmpth_k;
}

/* ascii field, space padded */
static void id_str(uint8_t *dst, const char *src, size_t len)
{
    size_t i;
    for (i = 0; i < len; i++)
        dst[i] = (src && *src) ? (uint8_t)*src++ : ' ';
}

static void identify_ctrl(uint8_t *d)
{
    char mn[41];
    size_t n;

    memset(d, 0, IDENTIFY_SIZE);
    put_le16(&d[0], FW_PCI_VID);
    put_le16(&d[2], FW_PCI_SSVID);
    memcpy(&d[4], g_ftl.serial, 20);

    /* MN = prefix + nand char + suffix, e.g. "SRK S4T NVMe SSD" */
    memset(mn, 0, sizeof(mn));
    n = strlen(FW_MODEL_PREFIX);
    memcpy(mn, FW_MODEL_PREFIX, n);
    mn[n++] = NAND_MODEL_CHAR;
    memcpy(mn + n, FW_MODEL_SUFFIX, strlen(FW_MODEL_SUFFIX));
    id_str(&d[24], mn, 40);
    id_str(&d[64], FW_REVISION, 8);

    d[72] = 0;                          /* RAB */
    d[73] = FW_IEEE_OUI0;
    d[74] = FW_IEEE_OUI1;
    d[75] = FW_IEEE_OUI2;
    d[77] = MDTS_SHIFT;
    put_le16(&d[78], 1);                /* CNTLID */
    put_le32(&d[80], FW_SPEC_VERSION);
    put_le16(&d[256], 0x0002);          /* OACS: format nvm */
    d[258] = 3;                         /* ACL */
    d[259] = 3;                         /* AERL */
    d[260] = 0x02;                      /* FRMW: 1 slot */
    d[261] = 0x02;                      /* LPA */
    d[262] = 63;                        /* ELPE */
    d[263] = FW_NPSS;
    put_le16(&d[266], TEMP_WCTEMP_K);
    put_le16(&d[268], TEMP_CCTEMP_K);
    d[512] = 0x66;                      /* SQES */
    d[513] = 0x44;                      /* CQES */
    put_le32(&d[516], 1);               /* NN */
    put_le16(&d[520], 0x0004);          /* ONCS: DSM */
    d[525] = 0x01;                      /* VWC present */

    /* power state descriptors (MP in centiwatts) */
    put_le16(&d[2048 + 0 * 32], 800);
    put_le16(&d[2048 + 1 * 32], 500);
    put_le16(&d[2048 + 2 * 32], 300);
}

static void identify_ns(uint8_t *d)
{
    memset(d, 0, IDENTIFY_SIZE);
    put_le64(&d[0],  g_ftl.capacity);   /* NSZE */
    put_le64(&d[8],  g_ftl.capacity);   /* NCAP */
    put_le64(&d[16], g_ftl.map_used);   /* NUSE (NAND 에 기록된 LBA) */
    d[24] = 0;                          /* NSFEAT */
    d[25] = 0;                          /* NLBAF (0's based) */
    d[26] = 0;                          /* FLBAS */
    d[32] = 0x01;                       /* DLFEAT: read 0 after dealloc */
    put_le32(&d[128], (uint32_t)LBA_SHIFT << 16);  /* LBAF0: LBADS=12, MS=0 */
}

static uint16_t adm_identify(const nvme_cmd_t *cmd, uint8_t *buf)
{
    uint32_t cns = cmd->cdw10 & 0xFF;

    if (buf == NULL)
        return ST_XFER_ERR;
    switch (cns) {
    case 0x00:
        if (cmd->nsid != 1)
            return ST_INV_NS;
        identify_ns(buf);
        return ST_OK;
    case 0x01:
        identify_ctrl(buf);
        return ST_OK;
    case 0x02:                          /* active namespace list */
        memset(buf, 0, IDENTIFY_SIZE);
        if (cmd->nsid < 1)
            put_le32(buf, 1);
        return ST_OK;
    default:
        return ST_INV_FIELD;
    }
}

static uint16_t adm_get_log(const nvme_cmd_t *cmd, uint8_t *buf)
{
    static uint8_t log[SMART_LOG_SIZE];
    uint32_t lid = cmd->cdw10 & 0xFF;
    uint32_t numd = ((cmd->cdw11 & 0xFFFF) << 16) | (cmd->cdw10 >> 16);
    uint32_t len = (numd + 1) * 4;

    if (lid != NVME_LOG_SMART)
        return ST_INV_LOG;
    if (buf == NULL)
        return ST_XFER_ERR;
    /* namespace 별 SMART 미지원 - nsid 무관하게 controller 값 */
    smart_build_log(log);
    memcpy(buf, log, MIN(len, (uint32_t)SMART_LOG_SIZE));
    return ST_OK;
}

static uint16_t adm_set_feat(const nvme_cmd_t *cmd, uint32_t *cdw0)
{
    uint32_t fid = cmd->cdw10 & 0xFF;
    uint32_t v = cmd->cdw11;

    if (cmd->cdw10 & BIT(31))
        return ST_NOT_SAVEABLE;

    switch (fid) {
    case NVME_FEAT_VWC:
        if (!(v & 1) && g_feat.vwc) {
            (void)WC_FlushAll();
            jrnl_commit(0, 0);
        }
        g_feat.vwc = (uint8_t)(v & 1);
        *cdw0 = g_feat.vwc;
        return ST_OK;
    case NVME_FEAT_TEMP_THRESH:
        if (((v >> 16) & 0xF) != 0 || ((v >> 20) & 0x3) != 0)
            return ST_INV_FIELD;        /* sensor 1개, over-temp 만 */
        g_feat.tmpth_k = (uint16_t)(v & 0xFFFF);
        return ST_OK;
    case NVME_FEAT_POWER_MGMT:
        if ((v & 0x1F) > FW_NPSS)
            return ST_INV_FIELD;
        g_feat.ps = (uint8_t)(v & 0x1F);
        return ST_OK;
    default:
        return ST_INV_FIELD;
    }
}

static uint16_t adm_get_feat(const nvme_cmd_t *cmd, uint32_t *cdw0)
{
    uint32_t fid = cmd->cdw10 & 0xFF;
    uint32_t sel = (cmd->cdw10 >> 8) & 0x7;
    int def;

    if (sel > 2)
        return ST_INV_FIELD;
    def = (sel != 0);                   /* saved 미지원 -> default 와 동일 */

    switch (fid) {
    case NVME_FEAT_VWC:
        *cdw0 = def ? 1 : g_feat.vwc;
        return ST_OK;
    case NVME_FEAT_TEMP_THRESH:
        if (((cmd->cdw11 >> 16) & 0xF) != 0 || ((cmd->cdw11 >> 20) & 0x3) != 0)
            return ST_INV_FIELD;
        *cdw0 = def ? TEMP_THRESH_DEF_K : g_feat.tmpth_k;
        return ST_OK;
    case NVME_FEAT_POWER_MGMT:
        *cdw0 = def ? 0 : g_feat.ps;
        return ST_OK;
    default:
        return ST_INV_FIELD;
    }
}

static uint16_t adm_format(const nvme_cmd_t *cmd)
{
    uint32_t lbaf = cmd->cdw10 & 0xF;
    uint32_t ses = (cmd->cdw10 >> 9) & 0x7;

    if (cmd->nsid != 1 && cmd->nsid != NSID_ALL)
        return ST_INV_NS;
    if (lbaf != 0)
        return ST_INV_FORMAT;
    if (ses > 1)
        return ST_INV_FIELD;            /* crypto erase 미지원 */

    LOGI("adm", "format nvm ses %u", ses);
    WC_DropAll();
    if (ftl_format((int)ses) != 0)
        return ST_INTERNAL;
    return ST_OK;
}

uint16_t nvme_admin_cmd(const nvme_cmd_t *cmd, void *buf, uint32_t *cdw0)
{
    switch (cmd->opcode) {
    case NVME_ADM_GET_LOG_PAGE:
        return adm_get_log(cmd, (uint8_t *)buf);
    case NVME_ADM_IDENTIFY:
        return adm_identify(cmd, (uint8_t *)buf);
    case NVME_ADM_SET_FEATURES:
        return adm_set_feat(cmd, cdw0);
    case NVME_ADM_GET_FEATURES:
        return adm_get_feat(cmd, cdw0);
    case NVME_ADM_FORMAT_NVM:
        return adm_format(cmd);
    case NVME_ADM_VS_DUMP_COUNTERS:
    case NVME_ADM_VS_SET_DEBUG:
        return nvme_vendor_cmd(cmd, buf, cdw0);
    default:
        LOGW("adm", "invalid admin opcode %02x", cmd->opcode);
        return ST_INV_OPC;
    }
}
