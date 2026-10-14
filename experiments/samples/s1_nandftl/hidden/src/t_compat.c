/* On-flash compatibility: write with one implementation, verify/append with another.
 * usage: t_compat write <seed> <img> | append <seed> <in> <out> | verify <seed> <img> <stage> */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "nfl/map.h"
#include "sim2.h"

static uint32_t vseed(unsigned s, unsigned v) { return s * 2477u + v * 104723u + 11u; }

/* expected version of sector s after stage (1 = after write, 2 = after append) */
static int expected(uint32_t seed, unsigned s, int stage)
{
	int v = 0;
	if (s < 150) v = 1;
	if (s % 5 == (seed % 5)) v = 0;               /* trimmed in stage 1 */
	if (stage >= 2) {
		if (s % 7 == 0 && s < 150) v = 2;          /* rewritten in stage 2 */
		if (s >= 150 && s < 180) v = 2;            /* new in stage 2 */
		if (s % 11 == 3) v = 0;                    /* trimmed in stage 2 */
	}
	return v;
}

int main(int argc, char **argv)
{
	if (argc < 4) return 2;
	uint32_t seed = (uint32_t)atoi(argv[2]);
	struct nfl_map m; nfl_error_t err = NFL_E_NONE;
	if (!strcmp(argv[1], "write")) {
		sim2_setup(10, 4, 80);
		sim2_inject_bad(seed, 4);
		uint8_t *pb = malloc(sim2_page_size()), *buf = malloc(sim2_page_size());
		nfl_map_init(&m, &sim2_nand, pb, 4);
		nfl_map_resume(&m, NULL);
		for (unsigned s = 0; s < 150; s++) { sim2_seq_gen(vseed(s, 1), buf, sim2_page_size()); if (nfl_map_write(&m, s, buf, &err) < 0) { printf("RESULT FAIL write err=%d\n", err); return 1; } }
		for (unsigned s = 0; s < 150; s++) if (s % 5 == (seed % 5)) nfl_map_trim(&m, s, &err);
		if (nfl_map_sync(&m, &err) < 0) { printf("RESULT FAIL sync\n"); return 1; }
		sim2_save(argv[3]);
		printf("RESULT OK\n");
		return 0;
	}
	if (!strcmp(argv[1], "append") && argc >= 5) {
		if (sim2_load(argv[3]) < 0) { printf("RESULT FAIL load\n"); return 1; }
		uint8_t *pb = malloc(sim2_page_size()), *buf = malloc(sim2_page_size());
		nfl_map_init(&m, &sim2_nand, pb, 4);
		if (nfl_map_resume(&m, &err) < 0) { printf("RESULT FAIL resume err=%d\n", err); return 1; }
		for (unsigned s = 0; s < 180; s++) {
			int v = 0;
			if ((s % 7 == 0 && s < 150) || (s >= 150 && s < 180)) v = 2;
			if (v) { sim2_seq_gen(vseed(s, 2), buf, sim2_page_size()); if (nfl_map_write(&m, s, buf, &err) < 0) { printf("RESULT FAIL append write err=%d\n", err); return 1; } }
		}
		for (unsigned s = 0; s < 180; s++) if (s % 11 == 3) nfl_map_trim(&m, s, &err);
		if (nfl_map_sync(&m, &err) < 0) { printf("RESULT FAIL sync\n"); return 1; }
		sim2_save(argv[4]);
		printf("RESULT OK\n");
		return 0;
	}
	if (!strcmp(argv[1], "verify") && argc >= 5) {
		int stage = atoi(argv[4]);
		if (sim2_load(argv[3]) < 0) { printf("RESULT FAIL load\n"); return 1; }
		uint8_t *pb = malloc(sim2_page_size()), *buf = malloc(sim2_page_size());
		nfl_map_init(&m, &sim2_nand, pb, 4);
		if (nfl_map_resume(&m, &err) < 0) { printf("RESULT FAIL resume err=%d\n", err); return 1; }
		unsigned bad = 0, cnt = 0;
		for (unsigned s = 0; s < 200; s++) {
			int v = expected(seed, s, stage);
			nfl_page_t loc;
			int r = nfl_map_find(&m, s, &loc, &err);
			if (v == 0) { if (r >= 0) bad++; continue; }
			cnt++;
			if (r < 0 || nfl_map_read(&m, s, buf, &err) < 0 || !sim2_seq_check(vseed(s, (unsigned)v), buf, sim2_page_size())) bad++;
		}
		if (nfl_map_size(&m) != cnt) bad++;
		printf("RESULT %s mismatches=%u size=%u expected=%u\n", bad ? "FAIL" : "OK", bad, (unsigned)nfl_map_size(&m), cnt);
		return bad ? 1 : 0;
	}
	return 2;
}
