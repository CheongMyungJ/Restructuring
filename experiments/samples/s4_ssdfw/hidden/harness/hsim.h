/*
 * hsim.h - hidden harness NAND / timer / temperature simulator.
 * Implements hal/hal_nand.h (+ hal_timer_ms, hal_temp_read) with the
 * production NAND geometry (TLC: 96 blocks x 48 pages x 16KiB, 64B spare).
 *
 * Fault injection is keyed by DATA SIGNATURES (implementation independent):
 *   a 4KiB host block whose bytes [16..31] are
 *     "@INJ" u32 type u32 param u32 id
 *   type 1 (RR): the NAND page that first stores this id needs read-retry
 *                level >= param to decode (param 99 = never)
 *   type 2 (PF): the first program of a page containing this id fails
 */
#ifndef HSIM_H
#define HSIM_H

#include <stdint.h>

#define HS_NBLK         96
#define HS_PPB          48
#define HS_PAGE         16384
#define HS_SPARE        64

#define INJ_RR          1
#define INJ_PF          2

void     hsim_reset(const uint32_t *bad, int nbad);
int      hsim_save(const char *path);
int      hsim_load(const char *path);
void     hsim_fail_next_erase(void);
void     hsim_arm_cut(uint32_t nops, void (*cb)(void));   /* cut on the (nops+1)th prog/erase */
void     hsim_disarm_cut(void);
uint32_t hsim_ops(void);                /* program + erase ops so far */
uint32_t hsim_violations(void);
void     hsim_set_temp(int32_t c);
void     hsim_advance(uint32_t ms);
int      hsim_age_ckpt(uint32_t ec);    /* patch latest checkpoint erase counts */

#endif
