/*
 * asic_regs.h - S4 controller (SRK-C400) register map
 *   ARM Cortex-R5 @ 500MHz, 4ch x 2way ONFI 4.0 NAND controller, PCIe Gen3 x4
 *   ref: C400 TRM rev 0.9 (2016.02)
 */
#ifndef ASIC_REGS_H
#define ASIC_REGS_H

#include <stdint.h>

#define REG32(addr)             (*(volatile uint32_t *)(uintptr_t)(addr))

/* ---- base addresses ---- */
#define SYSCTL_BASE             0x40000000u
#define TIMER_BASE              0x40001000u
#define UART_BASE               0x40002000u
#define I2C0_BASE               0x40003000u
#define GIC_DIST_BASE           0x40100000u
#define GIC_CPU_BASE            0x40101000u
#define NFC_BASE                0x41000000u     /* NAND flash controller */
#define NFC_CH_STRIDE           0x00010000u
#define ECC_BASE                0x41100000u
#define DMA_BASE                0x41200000u
#define NVME_BASE               0x42000000u     /* NVMe front-end (doorbell, SQ fetch) */
#define DRAM_BASE               0x80000000u     /* 512MiB DDR3 */

/* ---- SYSCTL ---- */
#define SYSCTL_CHIP_ID          REG32(SYSCTL_BASE + 0x000)      /* 0x0C400A01 */
#define SYSCTL_RST_CTRL         REG32(SYSCTL_BASE + 0x010)
#define SYSCTL_CLK_CTRL         REG32(SYSCTL_BASE + 0x020)
#define SYSCTL_PS_CTRL          REG32(SYSCTL_BASE + 0x030)      /* power state: core clk div */
#define SYSCTL_WDT_KICK         REG32(SYSCTL_BASE + 0x040)
#define SYSCTL_PLP_STATUS       REG32(SYSCTL_BASE + 0x050)      /* bit0: power fail detected */

/* ---- TIMER (1kHz tick) ---- */
#define TIMER_LOAD              REG32(TIMER_BASE + 0x00)
#define TIMER_VALUE             REG32(TIMER_BASE + 0x04)
#define TIMER_CTRL              REG32(TIMER_BASE + 0x08)
#define TIMER_INTCLR            REG32(TIMER_BASE + 0x0C)
#define TIMER_CTRL_EN           (1u << 7)
#define TIMER_CTRL_PERIODIC     (1u << 6)
#define TIMER_CTRL_IE           (1u << 5)

/* ---- I2C0 (temperature sensor TMP-75 compatible @0x48) ---- */
#define I2C_CTRL                REG32(I2C0_BASE + 0x00)
#define I2C_ADDR                REG32(I2C0_BASE + 0x04)
#define I2C_DATA                REG32(I2C0_BASE + 0x08)
#define I2C_STATUS              REG32(I2C0_BASE + 0x0C)
#define I2C_ST_BUSY             (1u << 0)
#define I2C_ST_NACK             (1u << 1)
#define TEMP_SENSOR_ADDR        0x48

/* ---- NFC per channel ---- */
#define NFC_CH(ch)              (NFC_BASE + (ch) * NFC_CH_STRIDE)
#define NFC_CMD(ch)             REG32(NFC_CH(ch) + 0x00)        /* command queue push */
#define NFC_ROW(ch)             REG32(NFC_CH(ch) + 0x04)        /* row address (blk|page) */
#define NFC_COL(ch)             REG32(NFC_CH(ch) + 0x08)
#define NFC_WAY(ch)             REG32(NFC_CH(ch) + 0x0C)
#define NFC_DMA_DESC(ch)        REG32(NFC_CH(ch) + 0x10)        /* descriptor address */
#define NFC_STATUS(ch)          REG32(NFC_CH(ch) + 0x14)
#define NFC_INT_STAT(ch)        REG32(NFC_CH(ch) + 0x18)
#define NFC_INT_EN(ch)          REG32(NFC_CH(ch) + 0x1C)
#define NFC_FEATURE(ch)         REG32(NFC_CH(ch) + 0x20)        /* SET FEATURE data (P1..P4) */
#define NFC_TIMING(ch)          REG32(NFC_CH(ch) + 0x30)

#define NFC_OP_READ             0x01
#define NFC_OP_PROGRAM          0x02
#define NFC_OP_ERASE            0x03
#define NFC_OP_SET_FEATURE      0x04
#define NFC_OP_READ_STATUS      0x05
#define NFC_OP_RESET            0x06
#define NFC_OP_READ_ID          0x07

#define NFC_ST_BUSY             (1u << 0)
#define NFC_ST_FAIL             (1u << 1)       /* NAND status bit0 (program/erase fail) */
#define NFC_ST_DONE             (1u << 2)
#define NFC_ST_TIMEOUT          (1u << 3)

#define NAND_FEAT_READ_RETRY    0x89            /* vendor read-retry option address */

/* ---- ECC (LDPC) ---- */
#define ECC_CTRL                REG32(ECC_BASE + 0x00)
#define ECC_RESULT(ch)          REG32(ECC_BASE + 0x10 + (ch) * 4)
#define ECC_RES_UNCORR          (1u << 31)
#define ECC_RES_ERASED          (1u << 30)      /* all-FF page detected */
#define ECC_RES_BITS(r)         ((r) & 0x3FF)

/* ---- DMA descriptor ---- */
typedef struct {
    uint32_t data_addr;         /* DRAM address of 16KiB data */
    uint32_t spare_addr;        /* DRAM address of OOB buffer */
    uint32_t len;               /* [15:0] data len, [31:16] spare len */
    uint32_t flags;             /* bit0 dir(1=to NAND) bit1 ecc bypass bit2 scramble */
    uint32_t next;              /* 0 = last */
    uint32_t status;            /* written by HW */
    uint32_t rsvd[2];
} nfc_desc_t;

#define DESC_DIR_WRITE          (1u << 0)
#define DESC_ECC_BYPASS         (1u << 1)
#define DESC_SCRAMBLE           (1u << 2)

/* ---- NVMe front-end ---- */
#define NVME_CC                 REG32(NVME_BASE + 0x14)
#define NVME_CSTS               REG32(NVME_BASE + 0x1C)
#define NVME_SQ_TAIL(q)         REG32(NVME_BASE + 0x1000 + (q) * 8)
#define NVME_CQ_HEAD(q)         REG32(NVME_BASE + 0x1004 + (q) * 8)
#define NVME_FE_INT_STAT        REG32(NVME_BASE + 0x2000)
#define NVME_FE_SQE_ADDR        REG32(NVME_BASE + 0x2010)       /* fetched SQE in SRAM */
#define NVME_FE_CQE_POST        REG32(NVME_BASE + 0x2020)
#define NVME_FE_PRP_XFER        REG32(NVME_BASE + 0x2030)

#define CC_SHN_MASK             (3u << 14)
#define CC_SHN_NORMAL           (1u << 14)
#define CC_SHN_ABRUPT           (2u << 14)
#define CSTS_RDY                (1u << 0)
#define CSTS_SHST_DONE          (2u << 2)

/* ---- interrupts ---- */
#define IRQ_TIMER0              32
#define IRQ_NFC0                40              /* 40..43 ch0..3 */
#define IRQ_NVME_FE             48
#define IRQ_PLP                 50

#endif /* ASIC_REGS_H */
