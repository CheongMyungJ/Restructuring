/*
 * nvme_int.h - host command layer internals
 */
#ifndef NVME_INT_H
#define NVME_INT_H

#include "fw_api.h"
#include "fw_types.h"

#define ST_OK               NVME_STATUS(0, NVME_SC_SUCCESS)
#define ST_INV_OPC          NVME_STATUS(0, NVME_SC_INVALID_OPCODE)
#define ST_INV_FIELD        NVME_STATUS(0, NVME_SC_INVALID_FIELD)
#define ST_XFER_ERR         NVME_STATUS(0, NVME_SC_DATA_XFER_ERROR)
#define ST_INTERNAL         NVME_STATUS(0, NVME_SC_INTERNAL)
#define ST_INV_NS           NVME_STATUS(0, NVME_SC_INVALID_NS)
#define ST_LBA_RANGE        NVME_STATUS(0, NVME_SC_LBA_RANGE)
#define ST_INV_LOG          NVME_STATUS(1, NVME_SC_INVALID_LOG_PAGE)
#define ST_INV_FORMAT       NVME_STATUS(1, NVME_SC_INVALID_FORMAT)
#define ST_NOT_SAVEABLE     NVME_STATUS(1, NVME_SC_FEAT_NOT_SAVEABLE)
#define ST_WRITE_FAULT      NVME_STATUS(2, NVME_SC_WRITE_FAULT)
#define ST_UNRECOVERED      NVME_STATUS(2, NVME_SC_UNRECOVERED_READ)

#define NSID_ALL            0xFFFFFFFFu
#define IDENTIFY_SIZE       4096
#define VS_DUMP_SIZE        512

/* volatile features (power-on default) */
typedef struct {
    uint8_t  vwc;           /* 0x06 */
    uint8_t  ps;            /* 0x02 */
    uint16_t tmpth_k;       /* 0x04 */
} nvme_feat_t;

extern nvme_feat_t g_feat;

void     nvme_feat_reset(void);
uint16_t nvme_feat_temp_thresh(void);
uint16_t nvme_admin_cmd(const nvme_cmd_t *cmd, void *buf, uint32_t *cdw0);
uint16_t nvme_io_cmd(const nvme_cmd_t *cmd, void *buf, uint32_t *cdw0);
uint16_t nvme_vendor_cmd(const nvme_cmd_t *cmd, void *buf, uint32_t *cdw0);

#endif
