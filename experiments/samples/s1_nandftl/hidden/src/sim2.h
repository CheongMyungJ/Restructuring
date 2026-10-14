/* Hidden NAND simulator for black-box tests (runtime geometry, power cut, images). */
#ifndef SIM2_H_
#define SIM2_H_
#include <stdint.h>
#include <stddef.h>
#include <setjmp.h>
#include "nfl/nand.h"

extern struct nfl_nand sim2_nand;
extern jmp_buf sim2_power_jmp;

struct sim2_stats {
	long is_bad, mark_bad, erase, erase_fail, is_free, prog, prog_fail,
	     read, read_bytes, copy;
};

void sim2_setup(int log2_page_size, int log2_ppb, int num_blocks);
void sim2_reset(void);
void sim2_inject_bad(uint32_t seed, int count);
void sim2_inject_failed(uint32_t seed, int count);
void sim2_inject_timebombs(uint32_t seed, int count, int max_ttl);
void sim2_set_power_cut(long ops);
int sim2_save(const char *path);
int sim2_load(const char *path);
const struct sim2_stats *sim2_get_stats(void);
void sim2_clear_stats(void);
const long *sim2_erase_counts(void);
int sim2_is_marked_bad(int blk);
int sim2_page_size(void);
uint32_t sim2_rand(uint32_t *state);
void sim2_seq_gen(uint32_t seed, uint8_t *buf, size_t len);
int sim2_seq_check(uint32_t seed, const uint8_t *buf, size_t len);
#endif
