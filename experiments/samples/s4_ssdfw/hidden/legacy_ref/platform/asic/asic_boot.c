/*
 * asic_boot.c - reset entry / main loop (Cortex-R5)
 *
 *  2016.04 jhkim
 */
#include "asic_regs.h"
#include "fw_api.h"
#include "fw_log.h"

extern void asic_clock_init(void);
extern void asic_ddr_init(void);
extern void asic_gic_init(void);
extern void asic_uart_init(uint32_t baud);
extern int  asic_poll_sq(void);
extern uint32_t asic_take_ticks(void);
extern int  asic_plp_detected(void);
extern void asic_set_power_state(uint32_t ps);

static void timer0_init(void)
{
    TIMER_LOAD = 500000u / 1000u;       /* 500MHz / 1000 -> wrong, prescaler 1/1000 applied by HW */
    TIMER_CTRL = TIMER_CTRL_EN | TIMER_CTRL_PERIODIC | TIMER_CTRL_IE;
}

static void handle_shutdown_request(void)
{
    uint32_t cc = NVME_CC;

    if ((cc & CC_SHN_MASK) == CC_SHN_NORMAL) {
        fw_shutdown(1);
        NVME_CSTS |= CSTS_SHST_DONE;
    } else if ((cc & CC_SHN_MASK) == CC_SHN_ABRUPT) {
        fw_shutdown(0);
        NVME_CSTS |= CSTS_SHST_DONE;
    }
}

int main(void)
{
    uint32_t t;
    int rc;

    asic_clock_init();
    asic_ddr_init();
    asic_uart_init(115200);
    asic_gic_init();
    timer0_init();

    rc = fw_init();
    if (rc != FW_OK) {
        LOGE("boot", "fw_init failed %d - entering safe mode", rc);
        for (;;)
            SYSCTL_WDT_KICK = 1;        /* safe mode: host sees CSTS.CFS */
    }
    NVME_CSTS |= CSTS_RDY;

    for (;;) {
        SYSCTL_WDT_KICK = 1;
        while (asic_poll_sq())
            ;
        t = asic_take_ticks();
        if (t)
            fw_tick(t);
        if (NVME_CC & CC_SHN_MASK)
            handle_shutdown_request();
        if (asic_plp_detected())
            for (;;)
                ;                       /* wait for power off */
        __asm__ volatile("wfi");
    }
    return 0;
}
