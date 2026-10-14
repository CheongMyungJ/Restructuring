/*
 * hal_nand.h - NAND HAL interface (FW -> platform)
 *
 * Implemented by platform/asic (real controller) and platform/sim (PC sim).
 * All calls are synchronous.  Block/page are physical indices.
 *
 *  - pages in a block must be programmed in ascending order, once per erase
 *  - data buffer = page_size bytes, spare buffer = spare_size bytes (OOB)
 *  - read: data or spare may be NULL (not transferred)
 *  - rr_level: 0 = default read, 1..15 = vendor read-retry option level
 *  - corrected_bits: bits corrected by ECC engine (may be NULL)
 *
 *  2016.03 jhkim
 *  2017.09 sypark  rr_level 파라미터 추가 (QLC)
 */
#ifndef HAL_NAND_H
#define HAL_NAND_H

#include <stdint.h>
#include "hal_timer.h"
#include "hal_temp.h"

#define HAL_NAND_OK             0
#define HAL_NAND_ECC_FAIL       1   /* uncorrectable at this read level */
#define HAL_NAND_BLANK          2   /* erased page (all 0xFF)            */
#define HAL_NAND_PROG_FAIL      3   /* program status fail               */
#define HAL_NAND_ERASE_FAIL     4   /* erase status fail                 */
#define HAL_NAND_BAD_PARAM      5

typedef struct {
    uint32_t num_blocks;
    uint32_t pages_per_block;
    uint32_t page_size;         /* data bytes per page (16384) */
    uint32_t spare_size;        /* OOB bytes usable by FW (>= 64) */
} hal_nand_geo_t;

void hal_nand_get_geometry(hal_nand_geo_t *geo);
int  hal_nand_read(uint32_t blk, uint32_t page, void *data, void *spare,
                   uint32_t rr_level, uint32_t *corrected_bits);
int  hal_nand_program(uint32_t blk, uint32_t page, const void *data, const void *spare);
int  hal_nand_erase(uint32_t blk);
int  hal_nand_is_bad(uint32_t blk);     /* factory bad block mark */

#endif /* HAL_NAND_H */
