/*
 * asic_isr.c - interrupt handlers + NVMe front-end glue
 *
 *  - TIMER0 1ms tick  -> s_tick_pending++ (main loop calls fw_tick)
 *  - NVMe FE          -> SQE fetched to SRAM, queued for main loop
 *  - PLP (power fail) -> fw_shutdown(0) path is too slow; only flag it
 *
 *  2016.04 jhkim
 *  2018.10 jhkim   tick 을 main loop 로 이동 (ISR 에서 GC 돌던 문제)
 */
#include "asic_regs.h"
#include "fw_api.h"
#include "fw_log.h"

#define SQE_RING_SIZE   64

typedef struct {
    uint32_t dw[16];
} sqe_t;

static volatile uint32_t s_ms;
static volatile uint32_t s_tick_pending;
static volatile uint32_t s_plp;
static sqe_t             s_sqe_ring[SQE_RING_SIZE];
static volatile uint32_t s_sqe_head, s_sqe_tail;

extern void gic_eoi(uint32_t irq);

uint32_t hal_timer_ms(void)
{
    return s_ms;
}

void isr_timer0(void)
{
    TIMER_INTCLR = 1;
    s_ms++;
    s_tick_pending++;
    gic_eoi(IRQ_TIMER0);
}

void isr_nvme_fe(void)
{
    uint32_t st = NVME_FE_INT_STAT;
    const volatile uint32_t *src;
    uint32_t i, next;

    if (st & 1) {                       /* SQE fetched */
        next = (s_sqe_tail + 1) % SQE_RING_SIZE;
        if (next != s_sqe_head) {
            src = (const volatile uint32_t *)(uintptr_t)NVME_FE_SQE_ADDR;
            for (i = 0; i < 16; i++)
                s_sqe_ring[s_sqe_tail].dw[i] = src[i];
            s_sqe_tail = next;
        }
    }
    if (st & 2) {                       /* CC.SHN written */
        /* handled in main loop via NVME_CC polling */
    }
    NVME_FE_INT_STAT = st;
    gic_eoi(IRQ_NVME_FE);
}

void isr_plp(void)
{
    s_plp = 1;                          /* 전원 차단 감지 - cap 없음, 할 수 있는 것 없음 */
    gic_eoi(IRQ_PLP);
}

/* SQE -> nvme_cmd_t (main loop context) */
static void sqe_to_cmd(const sqe_t *e, uint16_t sqid, nvme_cmd_t *c)
{
    c->sqid   = sqid;
    c->opcode = (uint8_t)(e->dw[0] & 0xFF);
    c->cid    = (uint16_t)(e->dw[0] >> 16);
    c->nsid   = e->dw[1];
    c->cdw10  = e->dw[10];
    c->cdw11  = e->dw[11];
    c->cdw12  = e->dw[12];
    c->cdw13  = e->dw[13];
    c->cdw14  = e->dw[14];
    c->cdw15  = e->dw[15];
    c->slba   = (uint64_t)e->dw[10] | ((uint64_t)e->dw[11] << 32);
    c->nlb    = e->dw[12] & 0xFFFF;
}

extern uint8_t *asic_prp_map(const sqe_t *e, uint32_t len);   /* asic_misc.c */
extern void     asic_prp_done(const sqe_t *e, int to_host);

int asic_poll_sq(void)
{
    static nvme_cmd_t cmd;
    static nvme_cpl_t cpl;
    const sqe_t *e;
    uint16_t sqid;
    uint8_t *buf;

    if (s_sqe_head == s_sqe_tail)
        return 0;
    e = &s_sqe_ring[s_sqe_head];
    sqid = (uint16_t)(e->dw[2] & 0xFFFF);       /* FE puts sqid in reserved dw2 */
    sqe_to_cmd(e, sqid, &cmd);
    buf = asic_prp_map(e, 0);
    fw_submit(&cmd, buf, &cpl);
    asic_prp_done(e, 1);
    NVME_FE_CQE_POST = ((uint32_t)cpl.status << 17) | cpl.cid;
    s_sqe_head = (s_sqe_head + 1) % SQE_RING_SIZE;
    return 1;
}

uint32_t asic_take_ticks(void)
{
    uint32_t t = s_tick_pending;
    s_tick_pending = 0;
    return t;
}

int asic_plp_detected(void)
{
    return (int)s_plp;
}
