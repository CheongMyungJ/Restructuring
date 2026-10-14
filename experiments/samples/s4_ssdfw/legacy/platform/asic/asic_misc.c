/*
 * asic_misc.c - temperature sensor, PRP mapping, power state, delay
 *
 *  2016.05 jhkim
 *  2018.11 mjlee   I2C temp sensor (보드 rev B 부터 TMP-75 호환)
 */
#include "asic_regs.h"
#include "hal_temp.h"
#include "fw_log.h"

#define PRP_BOUNCE_SIZE     (1024 * 1024)

static uint8_t s_prp_bounce[PRP_BOUNCE_SIZE] __attribute__((section(".dram"), aligned(4096)));

void asic_udelay(uint32_t us)
{
    volatile uint32_t n = us * 125;     /* ~4 cycles per loop @500MHz */
    while (n--)
        ;
}

static int i2c_read16(uint8_t addr, uint8_t reg, uint16_t *val)
{
    uint32_t t = 0;

    I2C_ADDR = ((uint32_t)addr << 1) | ((uint32_t)reg << 8);
    I2C_CTRL = 0x3;                     /* start + read 2 bytes */
    while (I2C_STATUS & I2C_ST_BUSY) {
        if (++t > 10000)
            return -1;
    }
    if (I2C_STATUS & I2C_ST_NACK)
        return -1;
    *val = (uint16_t)(I2C_DATA & 0xFFFF);
    return 0;
}

/* TMP-75: 12bit, 0.0625C/LSB, upper byte = integer degree */
int32_t hal_temp_read(void)
{
    static int32_t last = 40;
    uint16_t raw;

    if (i2c_read16(TEMP_SENSOR_ADDR, 0x00, &raw) != 0) {
        LOGW("temp", "sensor read fail, use last %d", last);
        return last;
    }
    last = (int32_t)(int8_t)(raw >> 8);
    return last;
}

/* PRP list 를 bounce buffer 로 (MDTS 1MiB) - FE DMA 가 host 메모리와 복사 */
uint8_t *asic_prp_map(const void *sqe, uint32_t len)
{
    const volatile uint32_t *dw = (const volatile uint32_t *)sqe;
    uint32_t opc = dw[0] & 0xFF;

    NVME_FE_PRP_XFER = (uint32_t)(uintptr_t)s_prp_bounce;
    if (opc == 0x01 || opc == 0x09 || opc == 0x81) {   /* host -> device */
        NVME_FE_PRP_XFER = 0x80000000u | (uint32_t)(uintptr_t)sqe;
        while (NVME_FE_PRP_XFER & 0x80000000u)
            ;
    }
    (void)len;
    return s_prp_bounce;
}

void asic_prp_done(const void *sqe, int to_host)
{
    if (!to_host)
        return;
    NVME_FE_PRP_XFER = 0x40000000u | (uint32_t)(uintptr_t)sqe;
    while (NVME_FE_PRP_XFER & 0x40000000u)
        ;
}

/* power state -> core clock divider (feature 0x02, 미연결: fw 에서 호출 안 함) */
void asic_set_power_state(uint32_t ps)
{
    static const uint32_t div[3] = { 1, 2, 4 };

    if (ps > 2)
        return;
    SYSCTL_PS_CTRL = div[ps];
}
