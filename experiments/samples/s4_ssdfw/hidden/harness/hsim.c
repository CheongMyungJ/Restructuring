/*
 * hsim.c - hidden harness HAL simulator (see hsim.h)
 * Deterministic.  Counts NAND protocol violations (program to a non-erased
 * page, out-of-order program, program/erase of a factory bad block, bad
 * address).  Power cut: the armed op is torn and the callback is invoked.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "hal/hal_nand.h"
#include "hsim.h"

#define PS_ERASED   0
#define PS_PROG     1
#define PS_TORN     2
#define PG_BYTES    (HS_PAGE + HS_SPARE)
#define MAX_IDS     8192

typedef struct {
    uint8_t *mem;               /* HS_PPB * PG_BYTES, lazily allocated */
    uint8_t  st[HS_PPB];
    uint8_t  lvl[HS_PPB];       /* required read-retry level, 0 = normal */
    uint32_t next;              /* next programmable page */
    uint8_t  bad;               /* factory bad */
} hblk_t;

static hblk_t   B[HS_NBLK];
static uint32_t s_ops, s_viol, s_cut_left;
static int      s_cut_armed, s_fail_erase;
static void   (*s_cut_cb)(void);
static uint32_t s_ids[MAX_IDS];
static int      s_nids;
static uint32_t s_ms;
static int32_t  s_temp = 40;

static uint32_t crc_tab[256];
static uint32_t hcrc32(const uint8_t *p, size_t n)
{
    uint32_t c = 0xFFFFFFFFu, i, j, k;
    if (!crc_tab[1])
        for (i = 0; i < 256; i++) {
            k = i;
            for (j = 0; j < 8; j++)
                k = (k & 1) ? (0xEDB88320u ^ (k >> 1)) : (k >> 1);
            crc_tab[i] = k;
        }
    while (n--)
        c = crc_tab[(c ^ *p++) & 0xFF] ^ (c >> 8);
    return c ^ 0xFFFFFFFFu;
}

static uint8_t *pg(uint32_t blk, uint32_t page)
{
    if (!B[blk].mem) {
        B[blk].mem = (uint8_t *)malloc((size_t)HS_PPB * PG_BYTES);
        if (!B[blk].mem) { fprintf(stderr, "hsim: oom\n"); exit(9); }
        memset(B[blk].mem, 0xFF, (size_t)HS_PPB * PG_BYTES);
    }
    return B[blk].mem + (size_t)page * PG_BYTES;
}

void hsim_reset(const uint32_t *bad, int nbad)
{
    int i;
    for (i = 0; i < HS_NBLK; i++)
        free(B[i].mem);
    memset(B, 0, sizeof(B));
    for (i = 0; i < nbad; i++)
        if (bad[i] < HS_NBLK)
            B[bad[i]].bad = 1;
    s_ops = s_viol = 0;
    s_cut_armed = s_fail_erase = 0;
    s_nids = 0;
    s_ms = 0;
    s_temp = 40;
}

static int id_used(uint32_t id)
{
    int i;
    for (i = 0; i < s_nids; i++)
        if (s_ids[i] == id)
            return 1;
    if (s_nids < MAX_IDS)
        s_ids[s_nids++] = id;
    return 0;
}

static int cut_now(void)
{
    if (!s_cut_armed)
        return 0;
    if (s_cut_left == 0) {
        s_cut_armed = 0;
        return 1;
    }
    s_cut_left--;
    return 0;
}

static void fire(void)
{
    if (s_cut_cb)
        s_cut_cb();
    fprintf(stderr, "hsim: power cut without handler\n");
    exit(8);
}

void hal_nand_get_geometry(hal_nand_geo_t *geo)
{
    geo->num_blocks = HS_NBLK;
    geo->pages_per_block = HS_PPB;
    geo->page_size = HS_PAGE;
    geo->spare_size = HS_SPARE;
}

int hal_nand_is_bad(uint32_t blk)
{
    if (blk >= HS_NBLK)
        return 1;
    return B[blk].bad;
}

int hal_nand_read(uint32_t blk, uint32_t page, void *data, void *spare,
                  uint32_t rr_level, uint32_t *corrected_bits)
{
    uint8_t st, *p;

    if (blk >= HS_NBLK || page >= HS_PPB) {
        s_viol++;
        return HAL_NAND_BAD_PARAM;
    }
    st = B[blk].mem ? B[blk].st[page] : PS_ERASED;
    if (corrected_bits)
        *corrected_bits = 0;
    if (st == PS_ERASED) {
        if (data) memset(data, 0xFF, HS_PAGE);
        if (spare) memset(spare, 0xFF, HS_SPARE);
        return HAL_NAND_BLANK;
    }
    if (st == PS_TORN || (B[blk].lvl[page] && rr_level < B[blk].lvl[page])) {
        if (data) memset(data, 0x5A, HS_PAGE);
        if (spare) memset(spare, 0x5A, HS_SPARE);
        return HAL_NAND_ECC_FAIL;
    }
    p = pg(blk, page);
    if (data) memcpy(data, p, HS_PAGE);
    if (spare) memcpy(spare, p + HS_PAGE, HS_SPARE);
    if (corrected_bits)
        *corrected_bits = B[blk].lvl[page] ? 30u + rr_level : 1u;
    return HAL_NAND_OK;
}

int hal_nand_program(uint32_t blk, uint32_t page, const void *data, const void *spare)
{
    const uint8_t *d = (const uint8_t *)data, *q;
    uint32_t s, type, param, id;
    uint8_t lvl = 0, *p;
    int pf = 0;

    if (blk >= HS_NBLK || page >= HS_PPB || data == NULL) {
        s_viol++;
        return HAL_NAND_BAD_PARAM;
    }
    if (B[blk].bad) {
        s_viol++;
        return HAL_NAND_PROG_FAIL;
    }
    p = pg(blk, page);
    if (page != B[blk].next || B[blk].st[page] != PS_ERASED) {
        s_viol++;
        return HAL_NAND_BAD_PARAM;
    }
    s_ops++;
    B[blk].next = page + 1;
    if (cut_now()) {
        B[blk].st[page] = PS_TORN;
        fire();
    }
    memcpy(p, d, HS_PAGE);
    if (spare)
        memcpy(p + HS_PAGE, spare, HS_SPARE);
    for (s = 0; s < 4; s++) {
        q = d + s * 4096 + 16;
        if (memcmp(q, "@INJ", 4) != 0)
            continue;
        memcpy(&type, q + 4, 4);
        memcpy(&param, q + 8, 4);
        memcpy(&id, q + 12, 4);
        if (id_used(id))
            continue;
        if (type == INJ_RR && param > lvl)
            lvl = (uint8_t)(param > 255 ? 255 : param);
        if (type == INJ_PF)
            pf = 1;
    }
    if (pf) {
        B[blk].st[page] = PS_TORN;
        return HAL_NAND_PROG_FAIL;
    }
    B[blk].st[page] = PS_PROG;
    B[blk].lvl[page] = lvl;
    return HAL_NAND_OK;
}

int hal_nand_erase(uint32_t blk)
{
    uint32_t i;

    if (blk >= HS_NBLK) {
        s_viol++;
        return HAL_NAND_BAD_PARAM;
    }
    if (B[blk].bad) {
        s_viol++;
        return HAL_NAND_ERASE_FAIL;
    }
    s_ops++;
    if (cut_now()) {
        (void)pg(blk, 0);
        for (i = 0; i < HS_PPB; i++)
            B[blk].st[i] = PS_TORN;
        B[blk].next = HS_PPB;
        fire();
    }
    if (s_fail_erase) {
        s_fail_erase = 0;
        return HAL_NAND_ERASE_FAIL;
    }
    memset(B[blk].st, PS_ERASED, sizeof(B[blk].st));
    memset(B[blk].lvl, 0, sizeof(B[blk].lvl));
    B[blk].next = 0;
    if (B[blk].mem)
        memset(B[blk].mem, 0xFF, (size_t)HS_PPB * PG_BYTES);
    return HAL_NAND_OK;
}

uint32_t hal_timer_ms(void) { return s_ms; }
int32_t  hal_temp_read(void) { return s_temp; }

void hsim_set_temp(int32_t c) { s_temp = c; }
void hsim_advance(uint32_t ms) { s_ms += ms; }
void hsim_fail_next_erase(void) { s_fail_erase = 1; }
uint32_t hsim_ops(void) { return s_ops; }
uint32_t hsim_violations(void) { return s_viol; }

void hsim_arm_cut(uint32_t nops, void (*cb)(void))
{
    s_cut_left = nops;
    s_cut_cb = cb;
    s_cut_armed = 1;
}

void hsim_disarm_cut(void) { s_cut_armed = 0; }

int hsim_save(const char *path)
{
    FILE *f = fopen(path, "wb");
    uint32_t hdr[5] = { HS_NBLK, HS_PPB, HS_PAGE, HS_SPARE, 0 }, b, p;
    uint16_t loc[2];

    if (!f)
        return -1;
    hdr[4] = (uint32_t)s_nids;
    fwrite("HSIMIMG1", 1, 8, f);
    fwrite(hdr, sizeof(hdr), 1, f);
    fwrite(s_ids, 4, (size_t)s_nids, f);
    for (b = 0; b < HS_NBLK; b++) {
        fwrite(&B[b].bad, 1, 1, f);
        fwrite(&B[b].next, 4, 1, f);
        fwrite(B[b].st, 1, HS_PPB, f);
        fwrite(B[b].lvl, 1, HS_PPB, f);
    }
    for (b = 0; b < HS_NBLK; b++)
        for (p = 0; p < HS_PPB; p++) {
            if (!B[b].mem || B[b].st[p] == PS_ERASED)
                continue;
            loc[0] = (uint16_t)b; loc[1] = (uint16_t)p;
            fwrite(loc, sizeof(loc), 1, f);
            fwrite(pg(b, p), PG_BYTES, 1, f);
        }
    loc[0] = loc[1] = 0xFFFF;
    fwrite(loc, sizeof(loc), 1, f);
    return fclose(f) == 0 ? 0 : -1;
}

int hsim_load(const char *path)
{
    FILE *f = fopen(path, "rb");
    char mg[8];
    uint32_t hdr[5], b;
    uint16_t loc[2];
    uint8_t st[HS_PPB];
    int ok = 1;

    if (!f)
        return -1;
    hsim_reset(NULL, 0);
    if (fread(mg, 1, 8, f) != 8 || memcmp(mg, "HSIMIMG1", 8) ||
        fread(hdr, sizeof(hdr), 1, f) != 1 || hdr[0] != HS_NBLK || hdr[1] != HS_PPB ||
        hdr[4] > MAX_IDS) {
        fclose(f);
        return -2;
    }
    s_nids = (int)hdr[4];
    ok &= fread(s_ids, 4, (size_t)s_nids, f) == (size_t)s_nids;
    for (b = 0; b < HS_NBLK && ok; b++) {
        ok &= fread(&B[b].bad, 1, 1, f) == 1;
        ok &= fread(&B[b].next, 4, 1, f) == 1;
        ok &= fread(st, 1, HS_PPB, f) == HS_PPB;
        ok &= fread(B[b].lvl, 1, HS_PPB, f) == HS_PPB;
        memcpy(B[b].st, st, HS_PPB);
    }
    while (ok && fread(loc, sizeof(loc), 1, f) == 1 && loc[0] != 0xFFFF) {
        if (loc[0] >= HS_NBLK || loc[1] >= HS_PPB) { ok = 0; break; }
        ok &= fread(pg(loc[0], loc[1]), PG_BYTES, 1, f) == 1;
    }
    fclose(f);
    return ok ? 0 : -3;
}

/*
 * Age the drive: patch the erase counts in the newest checkpoint part0
 * (on-NAND format 3.x: spare magic 0xA55A, type 0xC1, part u16 @12,
 * payload crc @20, spare crc @24 over [0..23]; part0 block table at 176,
 * 8 bytes per block {u32 ec, u8 state}).
 */
int hsim_age_ckpt(uint32_t ec)
{
    uint32_t b, p, seq, best_seq = 0, crc;
    uint8_t *best = NULL, *sp, *e;
    uint16_t magic, part;

    for (b = 2; b < 10; b++)
        for (p = 0; p < HS_PPB; p++) {
            if (!B[b].mem || B[b].st[p] != PS_PROG)
                continue;
            sp = pg(b, p) + HS_PAGE;
            memcpy(&magic, sp, 2);
            memcpy(&part, sp + 12, 2);
            memcpy(&seq, sp + 4, 4);
            if (magic != 0xA55A || sp[2] != 0xC1 || part != 0)
                continue;
            if (seq > best_seq) {
                best_seq = seq;
                best = pg(b, p);
            }
        }
    if (!best)
        return -1;
    for (b = 10; b < HS_NBLK; b++) {
        e = best + 176 + b * 8;
        if (e[4] == 2 || e[4] == 3)
            continue;
        memcpy(e, &ec, 4);
    }
    sp = best + HS_PAGE;
    crc = hcrc32(best, HS_PAGE);
    memcpy(sp + 20, &crc, 4);
    crc = hcrc32(sp, 24);
    memcpy(sp + 24, &crc, 4);
    return 0;
}
