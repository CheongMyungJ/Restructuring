/*
 * fw_api.h - host facing API of the S4 firmware (sim build)
 *
 * On the ASIC the NVMe front-end (platform/asic/asic_isr.c) fetches SQ entries,
 * converts them to nvme_cmd_t and calls fw_submit().  On the PC sim the test
 * tools call fw_submit() directly.  Everything is synchronous.
 *
 *  2016.04 jhkim   initial
 *  2017.02 hwchoi  vendor command 추가
 *  2018.10 jhkim   fw_tick() 추가 (background task 분리)
 */
#ifndef FW_API_H
#define FW_API_H

#include <stdint.h>

/* ---- admin opcodes (sqid == 0) ---- */
#define NVME_ADM_GET_LOG_PAGE       0x02
#define NVME_ADM_IDENTIFY           0x06
#define NVME_ADM_SET_FEATURES       0x09
#define NVME_ADM_GET_FEATURES       0x0A
#define NVME_ADM_FORMAT_NVM         0x80
#define NVME_ADM_VS_DUMP_COUNTERS   0xC0
#define NVME_ADM_VS_SET_DEBUG       0xC1

/* ---- I/O opcodes (sqid != 0) ---- */
#define NVME_IO_FLUSH               0x00
#define NVME_IO_WRITE               0x01
#define NVME_IO_READ                0x02
#define NVME_IO_DSM                 0x09

/* ---- feature ids ---- */
#define NVME_FEAT_POWER_MGMT        0x02
#define NVME_FEAT_TEMP_THRESH       0x04
#define NVME_FEAT_VWC               0x06

/* ---- log ids ---- */
#define NVME_LOG_SMART              0x02

/*
 * Command.  Field meaning follows NVMe where possible:
 *   slba / nlb : I/O commands (nlb is 0's based, like NVMe CDW12[15:0])
 *   cdw12 bit30: FUA (write)
 *   cdw10..15  : command specific (admin + DSM)
 */
typedef struct {
    uint16_t sqid;          /* 0 = admin queue, otherwise I/O queue */
    uint16_t cid;
    uint8_t  opcode;
    uint8_t  rsvd0[3];
    uint32_t nsid;
    uint64_t slba;
    uint32_t nlb;
    uint32_t cdw10;
    uint32_t cdw11;
    uint32_t cdw12;
    uint32_t cdw13;
    uint32_t cdw14;
    uint32_t cdw15;
} nvme_cmd_t;

/* Completion.  status = (SCT << 8) | SC */
typedef struct {
    uint32_t cdw0;
    uint16_t sqid;
    uint16_t cid;
    uint16_t status;
    uint16_t rsvd0;
} nvme_cpl_t;

#define NVME_STATUS(sct, sc)        ((uint16_t)((((sct) & 0x7) << 8) | ((sc) & 0xFF)))
#define NVME_SCT(st)                (((st) >> 8) & 0x7)
#define NVME_SC(st)                 ((st) & 0xFF)

/* generic (SCT 0) */
#define NVME_SC_SUCCESS             0x00
#define NVME_SC_INVALID_OPCODE      0x01
#define NVME_SC_INVALID_FIELD       0x02
#define NVME_SC_DATA_XFER_ERROR     0x04
#define NVME_SC_INTERNAL            0x06
#define NVME_SC_INVALID_NS          0x0B
#define NVME_SC_LBA_RANGE           0x80
/* command specific (SCT 1) */
#define NVME_SC_INVALID_LOG_PAGE    0x09
#define NVME_SC_INVALID_FORMAT      0x0A
#define NVME_SC_FEAT_NOT_SAVEABLE   0x0D
/* media (SCT 2) */
#define NVME_SC_WRITE_FAULT         0x80
#define NVME_SC_UNRECOVERED_READ    0x81

/* fw_init() return */
#define FW_OK                       0
#define FW_ERR_GEOMETRY             (-1)
#define FW_ERR_SUPERBLOCK           (-2)
#define FW_ERR_VERSION              (-3)
#define FW_ERR_NAND_TYPE            (-4)
#define FW_ERR_META                 (-5)

int  fw_init(void);                 /* power-on: mount / recover from NAND */
void fw_submit(const nvme_cmd_t *cmd, void *buf, nvme_cpl_t *cpl);
void fw_shutdown(int clean);        /* 1: normal shutdown (CC.SHN=01b), 0: abrupt (10b) */
void fw_tick(uint32_t ms);          /* background work, ms = elapsed time */

/* debug (sim tools only): FTL consistency check, returns error count */
int  fw_debug_check(void);

#endif /* FW_API_H */
