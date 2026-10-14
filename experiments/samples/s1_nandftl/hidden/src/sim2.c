#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sim2.h"

struct nfl_nand sim2_nand;
jmp_buf sim2_power_jmp;

#define F_BAD_MARK 0x01
#define F_FAILED   0x02

struct blk { int flags; int next_page; int timebomb; };

static int L2PS, L2PPB, NB, PS, PPB;
static struct blk *blocks;
static uint8_t *mem;
static long *erase_counts;
static struct sim2_stats st;
static long power_cut = -1;

uint32_t sim2_rand(uint32_t *s)
{
	uint32_t x = *s ? *s : 0x9e3779b9u;
	x ^= x << 13; x ^= x >> 17; x ^= x << 5;
	*s = x;
	return x;
}

void sim2_seq_gen(uint32_t seed, uint8_t *buf, size_t len)
{
	uint32_t s = seed * 2654435761u + 12345u;
	for (size_t i = 0; i < len; i++)
		buf[i] = (uint8_t)(sim2_rand(&s) >> 7);
}

int sim2_seq_check(uint32_t seed, const uint8_t *buf, size_t len)
{
	uint32_t s = seed * 2654435761u + 12345u;
	for (size_t i = 0; i < len; i++)
		if (buf[i] != (uint8_t)(sim2_rand(&s) >> 7))
			return 0;
	return 1;
}

void sim2_setup(int l2ps, int l2ppb, int nb)
{
	L2PS = l2ps; L2PPB = l2ppb; NB = nb;
	PS = 1 << l2ps; PPB = 1 << l2ppb;
	free(blocks); free(mem); free(erase_counts);
	blocks = calloc(NB, sizeof(*blocks));
	mem = malloc((size_t)NB * PPB * PS);
	erase_counts = calloc(NB, sizeof(long));
	sim2_nand.log2_page_size = (uint8_t)l2ps;
	sim2_nand.log2_ppb = (uint8_t)l2ppb;
	sim2_nand.num_blocks = (unsigned int)nb;
	sim2_reset();
}

void sim2_reset(void)
{
	memset(&st, 0, sizeof(st));
	memset(blocks, 0, sizeof(*blocks) * NB);
	memset(mem, 0x55, (size_t)NB * PPB * PS);
	memset(erase_counts, 0, sizeof(long) * NB);
	for (int i = 0; i < NB; i++)
		blocks[i].next_page = PPB;
	power_cut = -1;
}

static int pick_good(uint32_t *s)
{
	for (int tries = 0; tries < 100000; tries++) {
		int b = (int)(sim2_rand(s) % (uint32_t)NB);
		if (!blocks[b].flags && !blocks[b].timebomb)
			return b;
	}
	return -1;
}

void sim2_inject_bad(uint32_t seed, int count)
{
	uint32_t s = seed * 7919u + 1u;
	for (int i = 0; i < count; i++) {
		int b = pick_good(&s);
		if (b >= 0) blocks[b].flags |= F_BAD_MARK | F_FAILED;
	}
}

void sim2_inject_failed(uint32_t seed, int count)
{
	uint32_t s = seed * 104729u + 3u;
	for (int i = 0; i < count; i++) {
		int b = pick_good(&s);
		if (b >= 0) blocks[b].flags |= F_FAILED;
	}
}

void sim2_inject_timebombs(uint32_t seed, int count, int max_ttl)
{
	uint32_t s = seed * 1299709u + 7u;
	for (int i = 0; i < count; i++) {
		int b = pick_good(&s);
		if (b >= 0) blocks[b].timebomb = (int)(sim2_rand(&s) % (uint32_t)max_ttl) + 1;
	}
}

void sim2_set_power_cut(long ops) { power_cut = ops; }

static void power_tick(int is_prog, uint32_t where)
{
	if (power_cut < 0)
		return;
	if (power_cut == 0) {
		/* torn operation: leave garbage, then lose power */
		if (is_prog) {
			uint32_t blkno = where >> L2PPB;
			int pno = (int)(where & (uint32_t)(PPB - 1));
			sim2_seq_gen(where * 31u + 17u, mem + ((size_t)where << L2PS), (size_t)PS / 2);
			if (blocks[blkno].next_page <= pno)
				blocks[blkno].next_page = pno + 1;
		} else {
			sim2_seq_gen(where * 37u + 5u, mem + ((size_t)where << (L2PS + L2PPB)), (size_t)PS);
			blocks[where].next_page = PPB;
		}
		power_cut = -1;
		longjmp(sim2_power_jmp, 1);
	}
	power_cut--;
}

static void timebomb_tick(int b)
{
	if (blocks[b].timebomb) {
		blocks[b].timebomb--;
		if (!blocks[b].timebomb)
			blocks[b].flags |= F_FAILED;
	}
}

static void die(const char *what, long v)
{
	fprintf(stderr, "sim2: protocol violation: %s (%ld)\n", what, v);
	printf("SIM_VIOLATION %s %ld\n", what, v);
	fflush(stdout);
	exit(3);
}

int nfl_nand_is_bad(const struct nfl_nand *n, nfl_block_t b)
{
	(void)n;
	if (b >= (nfl_block_t)NB) die("is_bad invalid block", (long)b);
	st.is_bad++;
	return blocks[b].flags & F_BAD_MARK;
}

void nfl_nand_mark_bad(const struct nfl_nand *n, nfl_block_t b)
{
	(void)n;
	if (b >= (nfl_block_t)NB) die("mark_bad invalid block", (long)b);
	st.mark_bad++;
	blocks[b].flags |= F_BAD_MARK;
}

int nfl_nand_erase(const struct nfl_nand *n, nfl_block_t b, nfl_error_t *err)
{
	(void)n;
	if (b >= (nfl_block_t)NB) die("erase invalid block", (long)b);
	if (blocks[b].flags & F_BAD_MARK) die("erase on marked-bad block", (long)b);
	power_tick(0, b);
	st.erase++;
	erase_counts[b]++;
	blocks[b].next_page = 0;
	timebomb_tick((int)b);
	if (blocks[b].flags & F_FAILED) {
		st.erase_fail++;
		sim2_seq_gen(b * 57u + 29u, mem + ((size_t)b << (L2PS + L2PPB)), (size_t)PS * PPB);
		if (err) *err = NFL_E_BAD_BLOCK;
		return -1;
	}
	memset(mem + ((size_t)b << (L2PS + L2PPB)), 0xff, (size_t)PS * PPB);
	return 0;
}

int nfl_nand_prog(const struct nfl_nand *n, nfl_page_t p, const uint8_t *data, nfl_error_t *err)
{
	(void)n;
	uint32_t b = p >> L2PPB;
	int pno = (int)(p & (uint32_t)(PPB - 1));
	if (b >= (uint32_t)NB) die("prog invalid block", (long)b);
	if (blocks[b].flags & F_BAD_MARK) die("prog on marked-bad block", (long)b);
	if (pno < blocks[b].next_page) die("out-of-order/reprogram page", (long)p);
	power_tick(1, p);
	st.prog++;
	blocks[b].next_page = pno + 1;
	timebomb_tick((int)b);
	if (blocks[b].flags & F_FAILED) {
		st.prog_fail++;
		sim2_seq_gen(p * 57u + 29u, mem + ((size_t)p << L2PS), (size_t)PS);
		if (err) *err = NFL_E_BAD_BLOCK;
		return -1;
	}
	memcpy(mem + ((size_t)p << L2PS), data, (size_t)PS);
	return 0;
}

int nfl_nand_is_free(const struct nfl_nand *n, nfl_page_t p)
{
	(void)n;
	uint32_t b = p >> L2PPB;
	int pno = (int)(p & (uint32_t)(PPB - 1));
	if (b >= (uint32_t)NB) die("is_free invalid block", (long)b);
	st.is_free++;
	return blocks[b].next_page <= pno;
}

int nfl_nand_read(const struct nfl_nand *n, nfl_page_t p, size_t offset, size_t length,
		  uint8_t *data, nfl_error_t *err)
{
	(void)n; (void)err;
	uint32_t b = p >> L2PPB;
	if (b >= (uint32_t)NB) die("read invalid block", (long)b);
	if (offset > (size_t)PS || length > (size_t)PS || offset + length > (size_t)PS)
		die("read invalid range", (long)(offset + length));
	st.read++;
	st.read_bytes += (long)length;
	memcpy(data, mem + ((size_t)p << L2PS) + offset, length);
	return 0;
}

int nfl_nand_copy(const struct nfl_nand *n, nfl_page_t src, nfl_page_t dst, nfl_error_t *err)
{
	uint8_t *buf = malloc((size_t)PS);
	int r = 0;
	st.copy++;
	if (nfl_nand_read(n, src, 0, (size_t)PS, buf, err) < 0 ||
	    nfl_nand_prog(n, dst, buf, err) < 0)
		r = -1;
	free(buf);
	return r;
}

int sim2_save(const char *path)
{
	FILE *f = fopen(path, "wb");
	if (!f) return -1;
	int hdr[3] = { L2PS, L2PPB, NB };
	fwrite(hdr, sizeof(hdr), 1, f);
	fwrite(blocks, sizeof(*blocks), (size_t)NB, f);
	fwrite(mem, 1, (size_t)NB * PPB * PS, f);
	fclose(f);
	return 0;
}

int sim2_load(const char *path)
{
	FILE *f = fopen(path, "rb");
	if (!f) return -1;
	int hdr[3];
	if (fread(hdr, sizeof(hdr), 1, f) != 1) { fclose(f); return -1; }
	sim2_setup(hdr[0], hdr[1], hdr[2]);
	if (fread(blocks, sizeof(*blocks), (size_t)NB, f) != (size_t)NB ||
	    fread(mem, 1, (size_t)NB * PPB * PS, f) != (size_t)NB * PPB * PS) {
		fclose(f); return -1;
	}
	fclose(f);
	return 0;
}

const struct sim2_stats *sim2_get_stats(void) { return &st; }
void sim2_clear_stats(void) { memset(&st, 0, sizeof(st)); }
const long *sim2_erase_counts(void) { return erase_counts; }
int sim2_is_marked_bad(int b) { return blocks[b].flags & F_BAD_MARK; }
int sim2_page_size(void) { return PS; }
