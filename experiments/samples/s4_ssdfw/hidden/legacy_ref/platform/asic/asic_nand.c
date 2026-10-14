/*
 * asic_nand.c - hal_nand_* implementation on SRK-C400 NFC
 *
 * physical block number -> (channel, way, die block)
 *   ch  = blk % 4, way = (blk / 4) % 2, dblk = blk / 8
 * All operations are issued and polled synchronously (FW is single threaded).
 * Read retry: SET FEATURE 0x89 with retry option before the read, reset to 0 after.
 *
 *  2016.03 jhkim   initial (EVB)
 *  2017.09 sypark  read retry option (QLC)
 *  2018.03 dykang  timeout / NFC reset
 */
#include "asic_regs.h"
#include "hal_nand.h"
#include "nand_profile.h"
#include "fw_log.h"

#define NFC_CHANNELS            4
#define NFC_WAYS                2
#define NFC_TIMEOUT_US          20000           /* tBERS max 15ms */
#define ROW_ADDR(dblk, pg)      (((dblk) << 8) | (pg))

/* DMA descriptors + bounce buffers in TCM (non-cacheable) */
static nfc_desc_t s_desc[NFC_CHANNELS] __attribute__((section(".tcm"), aligned(32)));
static uint8_t s_spare_bounce[NFC_CHANNELS][NAND_SPARE_SIZE] __attribute__((section(".tcm")));

extern void asic_udelay(uint32_t us);
extern void dcache_clean_range(const void *p, uint32_t len);
extern void dcache_inval_range(const void *p, uint32_t len);

static inline void blk_decode(uint32_t blk, uint32_t *ch, uint32_t *way, uint32_t *dblk)
{
    *ch = blk % NFC_CHANNELS;
    *way = (blk / NFC_CHANNELS) % NFC_WAYS;
    *dblk = blk / (NFC_CHANNELS * NFC_WAYS);
}

static int nfc_wait(uint32_t ch)
{
    uint32_t t = 0;

    while (NFC_STATUS(ch) & NFC_ST_BUSY) {
        asic_udelay(1);
        if (++t > NFC_TIMEOUT_US) {
            LOGE("nfc", "ch%u timeout, reset", ch);
            NFC_CMD(ch) = NFC_OP_RESET;
            return -1;
        }
    }
    return (NFC_STATUS(ch) & NFC_ST_FAIL) ? 1 : 0;
}

static void nfc_set_rr(uint32_t ch, uint32_t way, uint32_t level)
{
    NFC_WAY(ch) = way;
    NFC_COL(ch) = NAND_FEAT_READ_RETRY;
    NFC_FEATURE(ch) = level & 0xFF;
    NFC_CMD(ch) = NFC_OP_SET_FEATURE;
    (void)nfc_wait(ch);
}

void hal_nand_get_geometry(hal_nand_geo_t *geo)
{
    /* EVB/양산 보드 모두 profile 값 사용 (ONFI parameter page 는 확인만) */
    geo->num_blocks = NAND_BLOCKS;
    geo->pages_per_block = NAND_PAGES_PER_BLK;
    geo->page_size = NAND_PAGE_SIZE;
    geo->spare_size = NAND_SPARE_SIZE;
}

int hal_nand_read(uint32_t blk, uint32_t page, void *data, void *spare,
                  uint32_t rr_level, uint32_t *corrected_bits)
{
    uint32_t ch, way, dblk, res;
    nfc_desc_t *d;
    int rc;

    if (blk >= NAND_BLOCKS || page >= NAND_PAGES_PER_BLK)
        return HAL_NAND_BAD_PARAM;
    blk_decode(blk, &ch, &way, &dblk);
    if (rr_level)
        nfc_set_rr(ch, way, rr_level);

    d = &s_desc[ch];
    d->data_addr = (uint32_t)(uintptr_t)data;
    d->spare_addr = (uint32_t)(uintptr_t)s_spare_bounce[ch];
    d->len = (data ? NAND_PAGE_SIZE : 0) | ((uint32_t)NAND_SPARE_SIZE << 16);
    d->flags = DESC_SCRAMBLE;
    d->next = 0;
    d->status = 0;
    dcache_clean_range(d, sizeof(*d));
    if (data)
        dcache_inval_range(data, NAND_PAGE_SIZE);

    NFC_WAY(ch) = way;
    NFC_ROW(ch) = ROW_ADDR(dblk, page);
    NFC_COL(ch) = 0;
    NFC_DMA_DESC(ch) = (uint32_t)(uintptr_t)d;
    NFC_CMD(ch) = NFC_OP_READ;
    rc = nfc_wait(ch);
    res = ECC_RESULT(ch);
    if (rr_level)
        nfc_set_rr(ch, way, 0);
    if (rc < 0)
        return HAL_NAND_ECC_FAIL;

    if (spare) {
        dcache_inval_range(s_spare_bounce[ch], NAND_SPARE_SIZE);
        __builtin_memcpy(spare, s_spare_bounce[ch], NAND_SPARE_SIZE);
    }
    if (corrected_bits)
        *corrected_bits = ECC_RES_BITS(res);
    if (res & ECC_RES_ERASED)
        return HAL_NAND_BLANK;
    if (res & ECC_RES_UNCORR)
        return HAL_NAND_ECC_FAIL;
    return HAL_NAND_OK;
}

int hal_nand_program(uint32_t blk, uint32_t page, const void *data, const void *spare)
{
    uint32_t ch, way, dblk;
    nfc_desc_t *d;
    int rc;

    if (blk >= NAND_BLOCKS || page >= NAND_PAGES_PER_BLK)
        return HAL_NAND_BAD_PARAM;
    blk_decode(blk, &ch, &way, &dblk);

    __builtin_memcpy(s_spare_bounce[ch], spare, NAND_SPARE_SIZE);
    d = &s_desc[ch];
    d->data_addr = (uint32_t)(uintptr_t)data;
    d->spare_addr = (uint32_t)(uintptr_t)s_spare_bounce[ch];
    d->len = NAND_PAGE_SIZE | ((uint32_t)NAND_SPARE_SIZE << 16);
    d->flags = DESC_DIR_WRITE | DESC_SCRAMBLE;
    d->next = 0;
    d->status = 0;
    dcache_clean_range(d, sizeof(*d));
    dcache_clean_range(data, NAND_PAGE_SIZE);
    dcache_clean_range(s_spare_bounce[ch], NAND_SPARE_SIZE);

    NFC_WAY(ch) = way;
    NFC_ROW(ch) = ROW_ADDR(dblk, page);
    NFC_COL(ch) = 0;
    NFC_DMA_DESC(ch) = (uint32_t)(uintptr_t)d;
    NFC_CMD(ch) = NFC_OP_PROGRAM;
    rc = nfc_wait(ch);
    return (rc == 0) ? HAL_NAND_OK : HAL_NAND_PROG_FAIL;
}

int hal_nand_erase(uint32_t blk)
{
    uint32_t ch, way, dblk;
    int rc;

    if (blk >= NAND_BLOCKS)
        return HAL_NAND_BAD_PARAM;
    blk_decode(blk, &ch, &way, &dblk);
    NFC_WAY(ch) = way;
    NFC_ROW(ch) = ROW_ADDR(dblk, 0);
    NFC_CMD(ch) = NFC_OP_ERASE;
    rc = nfc_wait(ch);
    return (rc == 0) ? HAL_NAND_OK : HAL_NAND_ERASE_FAIL;
}

/* factory bad mark: first byte of spare of page 0 != 0xFF (ECC bypass read) */
int hal_nand_is_bad(uint32_t blk)
{
    uint32_t ch, way, dblk;
    nfc_desc_t *d;

    if (blk >= NAND_BLOCKS)
        return 1;
    blk_decode(blk, &ch, &way, &dblk);
    d = &s_desc[ch];
    d->data_addr = 0;
    d->spare_addr = (uint32_t)(uintptr_t)s_spare_bounce[ch];
    d->len = (uint32_t)NAND_SPARE_SIZE << 16;
    d->flags = DESC_ECC_BYPASS;
    d->next = 0;
    dcache_clean_range(d, sizeof(*d));
    NFC_WAY(ch) = way;
    NFC_ROW(ch) = ROW_ADDR(dblk, 0);
    NFC_COL(ch) = NAND_PAGE_SIZE;
    NFC_DMA_DESC(ch) = (uint32_t)(uintptr_t)d;
    NFC_CMD(ch) = NFC_OP_READ;
    if (nfc_wait(ch) < 0)
        return 1;
    dcache_inval_range(s_spare_bounce[ch], NAND_SPARE_SIZE);
    return s_spare_bounce[ch][0] != 0xFF;
}
