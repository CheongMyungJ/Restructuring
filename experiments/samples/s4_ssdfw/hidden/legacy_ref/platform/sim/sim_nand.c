/*
 * sim_nand.c - NAND flash model for the PC simulation build
 *
 *  - block 단위 lazy allocation (data + spare)
 *  - program 은 page 순서대로만 허용 (위반 시 BAD_PARAM + 경고)
 *  - erased page read -> BLANK, torn page read -> ECC_FAIL
 *  - weak page: req_level 이상 read-retry level 에서만 읽힘
 *
 *  2018.10 jhkim
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "hal_nand.h"
#include "nand_profile.h"
#include "sim.h"

#define PS_ERASED   0
#define PS_PROG     1
#define PS_TORN     2

typedef struct {
    uint8_t *data;              /* ppb * page_size, NULL = never programmed */
    uint8_t *spare;             /* ppb * spare_size */
    uint8_t  pstate[NAND_PAGES_PER_BLK];
    uint8_t  weak[NAND_PAGES_PER_BLK];
    uint32_t next_page;
    uint8_t  bad;
} sblk_t;

static sblk_t   s_blk[NAND_BLOCKS];
static int      s_init;
static uint64_t s_nread, s_nprog, s_nerase;
static int      s_fail_prog, s_fail_erase;
static uint32_t s_cut_left;
static int      s_cut_armed;
static void   (*s_cut_cb)(void);

static void blk_alloc(sblk_t *b)
{
    if (b->data)
        return;
    b->data = (uint8_t *)malloc((size_t)NAND_PAGES_PER_BLK * NAND_PAGE_SIZE);
    b->spare = (uint8_t *)malloc((size_t)NAND_PAGES_PER_BLK * NAND_SPARE_SIZE);
    if (!b->data || !b->spare) {
        fprintf(stderr, "sim: out of memory\n");
        exit(2);
    }
    memset(b->data, 0xFF, (size_t)NAND_PAGES_PER_BLK * NAND_PAGE_SIZE);
    memset(b->spare, 0xFF, (size_t)NAND_PAGES_PER_BLK * NAND_SPARE_SIZE);
}

int sim_nand_init(const uint32_t *bad_list, int nbad)
{
    int i;

    sim_nand_free();
    for (i = 0; i < nbad; i++)
        if (bad_list[i] < NAND_BLOCKS)
            s_blk[bad_list[i]].bad = 1;
    s_init = 1;
    return 0;
}

void sim_nand_free(void)
{
    int i;

    for (i = 0; i < NAND_BLOCKS; i++) {
        free(s_blk[i].data);
        free(s_blk[i].spare);
    }
    memset(s_blk, 0, sizeof(s_blk));
    s_nread = s_nprog = s_nerase = 0;
    s_fail_prog = s_fail_erase = 0;
    s_cut_armed = 0;
}

/* returns 1 if power is cut on this op */
static int cut_check(void)
{
    if (!s_cut_armed)
        return 0;
    if (s_cut_left > 0) {
        s_cut_left--;
        return 0;
    }
    return 1;
}

static void cut_fire(void)
{
    s_cut_armed = 0;
    if (s_cut_cb)
        s_cut_cb();
    fprintf(stderr, "sim: power cut (no handler)\n");
    exit(3);
}

void hal_nand_get_geometry(hal_nand_geo_t *geo)
{
    geo->num_blocks = NAND_BLOCKS;
    geo->pages_per_block = NAND_PAGES_PER_BLK;
    geo->page_size = NAND_PAGE_SIZE;
    geo->spare_size = NAND_SPARE_SIZE;
}

int hal_nand_read(uint32_t blk, uint32_t page, void *data, void *spare,
                  uint32_t rr_level, uint32_t *corrected_bits)
{
    sblk_t *b;
    uint8_t st;

    if (!s_init || blk >= NAND_BLOCKS || page >= NAND_PAGES_PER_BLK)
        return HAL_NAND_BAD_PARAM;
    b = &s_blk[blk];
    s_nread++;
    if (corrected_bits)
        *corrected_bits = 0;
    st = b->data ? b->pstate[page] : PS_ERASED;

    if (st == PS_ERASED) {
        if (data) memset(data, 0xFF, NAND_PAGE_SIZE);
        if (spare) memset(spare, 0xFF, NAND_SPARE_SIZE);
        return HAL_NAND_BLANK;
    }
    if (st == PS_TORN || (b->weak[page] && rr_level < b->weak[page])) {
        if (data) memset(data, 0xA5, NAND_PAGE_SIZE);
        if (spare) memset(spare, 0xA5, NAND_SPARE_SIZE);
        return HAL_NAND_ECC_FAIL;
    }
    if (data) memcpy(data, b->data + (size_t)page * NAND_PAGE_SIZE, NAND_PAGE_SIZE);
    if (spare) memcpy(spare, b->spare + (size_t)page * NAND_SPARE_SIZE, NAND_SPARE_SIZE);
    if (corrected_bits)
        *corrected_bits = b->weak[page] ? 40u + rr_level : 2u;
    return HAL_NAND_OK;
}

int hal_nand_program(uint32_t blk, uint32_t page, const void *data, const void *spare)
{
    sblk_t *b;

    if (!s_init || blk >= NAND_BLOCKS || page >= NAND_PAGES_PER_BLK)
        return HAL_NAND_BAD_PARAM;
    b = &s_blk[blk];
    if (b->bad || page != b->next_page) {
        fprintf(stderr, "sim: illegal program blk %u page %u (next %u bad %u)\n",
                blk, page, b->next_page, b->bad);
        return HAL_NAND_BAD_PARAM;
    }
    blk_alloc(b);
    s_nprog++;
    b->next_page = page + 1;
    if (cut_check()) {
        b->pstate[page] = PS_TORN;
        cut_fire();
    }
    memcpy(b->data + (size_t)page * NAND_PAGE_SIZE, data, NAND_PAGE_SIZE);
    if (spare)
        memcpy(b->spare + (size_t)page * NAND_SPARE_SIZE, spare, NAND_SPARE_SIZE);
    if (s_fail_prog) {
        s_fail_prog = 0;
        b->pstate[page] = PS_TORN;
        return HAL_NAND_PROG_FAIL;
    }
    b->pstate[page] = PS_PROG;
    return HAL_NAND_OK;
}

int hal_nand_erase(uint32_t blk)
{
    sblk_t *b;
    uint32_t p;

    if (!s_init || blk >= NAND_BLOCKS)
        return HAL_NAND_BAD_PARAM;
    b = &s_blk[blk];
    if (b->bad)
        return HAL_NAND_ERASE_FAIL;
    s_nerase++;
    if (cut_check()) {
        blk_alloc(b);
        for (p = 0; p < NAND_PAGES_PER_BLK; p++)
            b->pstate[p] = PS_TORN;     /* 중단된 erase: 내용 불명 */
        b->next_page = 0;
        cut_fire();
    }
    if (s_fail_erase) {
        s_fail_erase = 0;
        return HAL_NAND_ERASE_FAIL;
    }
    if (b->data) {
        memset(b->data, 0xFF, (size_t)NAND_PAGES_PER_BLK * NAND_PAGE_SIZE);
        memset(b->spare, 0xFF, (size_t)NAND_PAGES_PER_BLK * NAND_SPARE_SIZE);
    }
    memset(b->pstate, PS_ERASED, sizeof(b->pstate));
    memset(b->weak, 0, sizeof(b->weak));
    b->next_page = 0;
    return HAL_NAND_OK;
}

int hal_nand_is_bad(uint32_t blk)
{
    if (blk >= NAND_BLOCKS)
        return 1;
    return s_blk[blk].bad;
}

void sim_nand_set_weak(uint32_t blk, uint32_t page, uint32_t req_level)
{
    if (blk < NAND_BLOCKS && page < NAND_PAGES_PER_BLK)
        s_blk[blk].weak[page] = (uint8_t)(req_level > 255 ? 255 : req_level);
}

void sim_nand_fail_next_program(void) { s_fail_prog = 1; }
void sim_nand_fail_next_erase(void)   { s_fail_erase = 1; }

void sim_nand_stats(uint64_t *reads, uint64_t *progs, uint64_t *erases)
{
    if (reads) *reads = s_nread;
    if (progs) *progs = s_nprog;
    if (erases) *erases = s_nerase;
}

int sim_nand_page_state(uint32_t blk, uint32_t page)
{
    if (blk >= NAND_BLOCKS || page >= NAND_PAGES_PER_BLK || !s_blk[blk].data)
        return PS_ERASED;
    return s_blk[blk].pstate[page];
}

const uint8_t *sim_nand_page_data(uint32_t blk, uint32_t page)
{
    if (sim_nand_page_state(blk, page) == PS_ERASED)
        return NULL;
    return s_blk[blk].data + (size_t)page * NAND_PAGE_SIZE;
}

const uint8_t *sim_nand_page_spare(uint32_t blk, uint32_t page)
{
    if (sim_nand_page_state(blk, page) == PS_ERASED)
        return NULL;
    return s_blk[blk].spare + (size_t)page * NAND_SPARE_SIZE;
}

void sim_power_cut_after(uint32_t nops, void (*cb)(void))
{
    s_cut_left = nops;
    s_cut_cb = cb;
    s_cut_armed = 1;
}

void sim_power_cut_cancel(void)
{
    s_cut_armed = 0;
}

/* ---- image file: "S4SIMIMG" ver geometry, then per block records ---- */
#define IMG_MAGIC   "S4SIMIMG"
#define IMG_VER     2

int sim_nand_save(const char *path)
{
    FILE *f = fopen(path, "wb");
    uint32_t hdr[6], i;
    sblk_t *b;

    if (!f)
        return -1;
    hdr[0] = IMG_VER; hdr[1] = NAND_BLOCKS; hdr[2] = NAND_PAGES_PER_BLK;
    hdr[3] = NAND_PAGE_SIZE; hdr[4] = NAND_SPARE_SIZE; hdr[5] = NAND_TYPE_ID;
    fwrite(IMG_MAGIC, 1, 8, f);
    fwrite(hdr, sizeof(hdr), 1, f);
    for (i = 0; i < NAND_BLOCKS; i++) {
        b = &s_blk[i];
        fwrite(&b->bad, 1, 1, f);
        fwrite(&b->next_page, 4, 1, f);
        fwrite(b->pstate, 1, NAND_PAGES_PER_BLK, f);
        fwrite(b->weak, 1, NAND_PAGES_PER_BLK, f);
        if (b->data) {
            fputc(1, f);
            fwrite(b->data, NAND_PAGE_SIZE, NAND_PAGES_PER_BLK, f);
            fwrite(b->spare, NAND_SPARE_SIZE, NAND_PAGES_PER_BLK, f);
        } else {
            fputc(0, f);
        }
    }
    fclose(f);
    return 0;
}

int sim_nand_load(const char *path)
{
    FILE *f = fopen(path, "rb");
    char mg[8];
    uint32_t hdr[6], i;
    sblk_t *b;
    int has, ok = 1;

    if (!f)
        return -1;
    if (fread(mg, 1, 8, f) != 8 || memcmp(mg, IMG_MAGIC, 8) != 0 ||
        fread(hdr, sizeof(hdr), 1, f) != 1 || hdr[0] != IMG_VER ||
        hdr[1] != NAND_BLOCKS || hdr[2] != NAND_PAGES_PER_BLK) {
        fclose(f);
        return -2;
    }
    sim_nand_free();
    for (i = 0; i < NAND_BLOCKS && ok; i++) {
        b = &s_blk[i];
        ok &= fread(&b->bad, 1, 1, f) == 1;
        ok &= fread(&b->next_page, 4, 1, f) == 1;
        ok &= fread(b->pstate, 1, NAND_PAGES_PER_BLK, f) == NAND_PAGES_PER_BLK;
        ok &= fread(b->weak, 1, NAND_PAGES_PER_BLK, f) == NAND_PAGES_PER_BLK;
        has = fgetc(f);
        if (has == 1) {
            blk_alloc(b);
            ok &= fread(b->data, NAND_PAGE_SIZE, NAND_PAGES_PER_BLK, f) == NAND_PAGES_PER_BLK;
            ok &= fread(b->spare, NAND_SPARE_SIZE, NAND_PAGES_PER_BLK, f) == NAND_PAGES_PER_BLK;
        }
    }
    fclose(f);
    s_init = 1;
    return ok ? 0 : -3;
}
