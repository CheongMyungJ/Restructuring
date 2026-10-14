/*
 * sim.h - PC simulation platform control (dev team only)
 *
 *  NAND model: page data + spare, erase, factory bad blocks, weak page
 *  (read-retry level needed), program/erase fail injection, power cut
 *  injection, image save/load.
 *
 *  2018.10 jhkim   (was nand_emu.c in S3)
 */
#ifndef SIM_H
#define SIM_H

#include <stdint.h>

#define SIM_LVL_DEAD        99      /* weak level: never recoverable */

int  sim_nand_init(const uint32_t *bad_list, int nbad);
void sim_nand_free(void);
int  sim_nand_save(const char *path);
int  sim_nand_load(const char *path);

void sim_nand_set_weak(uint32_t blk, uint32_t page, uint32_t req_level);
void sim_nand_fail_next_program(void);
void sim_nand_fail_next_erase(void);
void sim_nand_stats(uint64_t *reads, uint64_t *progs, uint64_t *erases);
int  sim_nand_page_state(uint32_t blk, uint32_t page);    /* 0 erased 1 prog 2 torn */
const uint8_t *sim_nand_page_data(uint32_t blk, uint32_t page);
const uint8_t *sim_nand_page_spare(uint32_t blk, uint32_t page);

/* power cut: after n more program/erase ops the op is torn and cb() is
 * called (cb must not return - longjmp back to the test loop) */
void sim_power_cut_after(uint32_t nops, void (*cb)(void));
void sim_power_cut_cancel(void);

void sim_set_temp(int32_t c);
void sim_advance_ms(uint32_t ms);

#endif
