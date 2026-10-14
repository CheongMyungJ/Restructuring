/* Deterministic trace compared against the legacy firmware's trace.
 * HARD lines must match exactly; SOFT lines are compared with tolerance. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "nfl/map.h"
#include "sim2.h"

static uint8_t *pb, *buf;

static void reboot(struct nfl_map *m, int gc, int *r, nfl_error_t *e)
{
	nfl_error_t err = NFL_E_NONE;
	nfl_map_init(m, &sim2_nand, pb, (uint8_t)gc);
	int rr = nfl_map_resume(m, &err);
	if (r) *r = rr;
	if (e) *e = err;
}

static void alloc_bufs(void)
{
	free(pb); free(buf);
	pb = malloc(sim2_page_size()); buf = malloc(sim2_page_size());
}

static void capacity_table(void)
{
	const int geo[][3] = { {9,3,113}, {9,4,64}, {11,6,32}, {10,5,200}, {12,2,300} };
	const int gcs[] = { 1, 4, 16 };
	for (unsigned g = 0; g < sizeof(geo)/sizeof(geo[0]); g++)
		for (unsigned k = 0; k < 3; k++)
			for (int bad = 0; bad <= 5; bad += 5) {
				sim2_setup(geo[g][0], geo[g][1], geo[g][2]);
				alloc_bufs();
				sim2_inject_bad(g * 10 + k, bad);
				struct nfl_map m; int r; nfl_error_t e;
				reboot(&m, gcs[k], &r, &e);
				printf("HARD CAP ps=%d ppb=%d nb=%d gc=%d bad=%d -> cap=%u resume=%d\n",
				       geo[g][0], geo[g][1], geo[g][2], gcs[k], bad,
				       (unsigned)nfl_map_capacity(&m), r);
			}
}

static void fill_to_full(int gc)
{
	sim2_setup(9, 3, 48);
	alloc_bufs();
	struct nfl_map m; nfl_error_t err = NFL_E_NONE;
	reboot(&m, gc, NULL, NULL);
	unsigned n = 0;
	for (;;) {
		sim2_seq_gen(n + 5u, buf, sim2_page_size());
		if (nfl_map_write(&m, n, buf, &err) < 0) break;
		n++;
		if (n > 100000) break;
	}
	printf("HARD FILL gc=%d written=%u err=%d size=%u cap=%u\n", gc, n, (int)err,
	       (unsigned)nfl_map_size(&m), (unsigned)nfl_map_capacity(&m));
	/* rewriting an existing sector at full capacity */
	sim2_seq_gen(777u, buf, sim2_page_size());
	int r = nfl_map_write(&m, 0, buf, &err);
	printf("HARD FILL_REWRITE gc=%d r=%d err=%d\n", gc, r, r < 0 ? (int)err : 0);
	nfl_map_sync(&m, NULL);
	reboot(&m, gc, NULL, NULL);
	unsigned ok = 0;
	for (unsigned i = 0; i < n; i++)
		if (nfl_map_read(&m, i, buf, &err) == 0 && sim2_seq_check(i == 0 && r == 0 ? 777u : i + 5u, buf, sim2_page_size())) ok++;
	printf("HARD FILL_VERIFY gc=%d ok=%u/%u\n", gc, ok, n);
}

/* Versioned writes: data seed encodes (sector, version) */
static uint32_t vseed(unsigned s, unsigned v) { return s * 131u + v * 7919u + 3u; }

static int sector_version(struct nfl_map *m, unsigned s)
{
	nfl_error_t err;
	nfl_page_t loc;
	if (nfl_map_find(m, s, &loc, &err) < 0) return err == NFL_E_NOT_FOUND ? 0 : 8;
	if (nfl_map_read(m, s, buf, &err) < 0) return 8;
	for (unsigned v = 1; v <= 4; v++)
		if (sim2_seq_check(vseed(s, v), buf, sim2_page_size())) return (int)v;
	return 9;
}

static void power_cut_scenario(uint32_t seed, long cut)
{
	sim2_setup(9, 3, 64);
	alloc_bufs();
	sim2_inject_bad(seed, 3);
	struct nfl_map m; nfl_error_t err; int r;
	reboot(&m, 4, NULL, NULL);
	for (unsigned s = 0; s < 60; s++) { sim2_seq_gen(vseed(s, 1), buf, sim2_page_size()); nfl_map_write(&m, s, buf, &err); }
	nfl_map_sync(&m, NULL);
	int cut_hit = 1;
	sim2_set_power_cut(cut);
	if (setjmp(sim2_power_jmp) == 0) {
		uint32_t st = seed + 1;
		for (int i = 0; i < 40; i++) {
			unsigned s = sim2_rand(&st) % 60;
			sim2_seq_gen(vseed(s, 2), buf, sim2_page_size());
			nfl_map_write(&m, s, buf, &err);
			if (i == 25) nfl_map_sync(&m, NULL);
		}
		for (unsigned s = 0; s < 10; s++) nfl_map_trim(&m, s * 3, &err);
		for (unsigned s = 60; s < 80; s++) { sim2_seq_gen(vseed(s, 3), buf, sim2_page_size()); nfl_map_write(&m, s, buf, &err); }
		cut_hit = 0;
	}
	sim2_set_power_cut(-1);
	reboot(&m, 4, &r, NULL);
	char map[81];
	for (unsigned s = 0; s < 80; s++) map[s] = (char)('0' + sector_version(&m, s));
	map[80] = 0;
	printf("HARD PL seed=%u cut=%ld hit=%d resume=%d size=%u map=%s\n", seed, cut, cut_hit, r,
	       (unsigned)nfl_map_size(&m), map);
}

static void workload_ops(void)
{
	sim2_setup(9, 3, 96);
	alloc_bufs();
	sim2_inject_bad(4242, 4);
	struct nfl_map m; nfl_error_t err;
	reboot(&m, 4, NULL, NULL);
	unsigned cap = nfl_map_capacity(&m);
	unsigned range = cap / 2;
	sim2_clear_stats();
	uint32_t st = 31337;
	for (int i = 0; i < 4000; i++) {
		unsigned s = sim2_rand(&st) % range;
		sim2_seq_gen(vseed(s, 1) + (uint32_t)i, buf, sim2_page_size());
		if (nfl_map_write(&m, s, buf, &err) < 0) { printf("HARD WORKLOAD write_error i=%d err=%d\n", i, (int)err); break; }
		if (i % 100 == 99) nfl_map_sync(&m, NULL);
	}
	const struct sim2_stats *ss = sim2_get_stats();
	printf("SOFT OPS prog=%ld erase=%ld\n", ss->prog, ss->erase);
	printf("INFO OPS read=%ld read_bytes=%ld copy=%ld is_free=%ld is_bad=%ld\n", ss->read, ss->read_bytes, ss->copy, ss->is_free, ss->is_bad);
	const long *ec = sim2_erase_counts();
	long mn = 1L << 30, mx = 0;
	for (int b = 0; b < 96; b++) {
		if (sim2_is_marked_bad(b)) continue;
		if (ec[b] < mn) mn = ec[b];
		if (ec[b] > mx) mx = ec[b];
	}
	printf("SOFT WEAR spread=%ld\n", mx - mn);
	printf("HARD WORKLOAD size=%u\n", (unsigned)nfl_map_size(&m));
}

int main(void)
{
	capacity_table();
	fill_to_full(1);
	fill_to_full(4);
	fill_to_full(16);
	const long cuts[] = { 0, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89 };
	for (uint32_t seed = 1; seed <= 3; seed++)
		for (unsigned i = 0; i < sizeof(cuts)/sizeof(cuts[0]); i++)
			power_cut_scenario(seed, cuts[i]);
	workload_ops();
	return 0;
}
