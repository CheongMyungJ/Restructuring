/*
 * nand_profile.h - NAND 타입별 파라미터 (geometry / endurance / read-retry)
 *
 *  2016.03  jhkim   TLC profile (T-gen2)
 *  2017.08  sypark  QLC profile 추가 (Q-gen1 샘플)
 *  2018.06  sypark  RR table 순서 vendor 권고값으로 변경
 *
 * geometry 값은 sim/asic platform 이 NAND 를 구성할 때 사용한다.
 * FTL 은 실제 geometry 를 hal_nand_get_geometry() 로 읽는다.
 */
#ifndef NAND_PROFILE_H
#define NAND_PROFILE_H

#include "fw_config.h"

#define NAND_PAGE_SIZE          16384
#define NAND_SPARE_SIZE         64

#if CFG_NAND_TYPE == TLC

#define NAND_TYPE_ID            1
#define NAND_TYPE_NAME          "TLC"
#define NAND_MODEL_CHAR         'T'
#define NAND_BLOCKS             96
#define NAND_PAGES_PER_BLK      48          /* 16 WL x 3 */
#define NAND_PE_LIMIT           3000
#define NAND_RR_MAX             7
#define NAND_RR_TABLE           { 1, 2, 3, 4, 5, 6, 7 }
#define NAND_RR_REFRESH_LVL     4           /* success at >= this level -> refresh */
#define NAND_RD_LIMIT           20000       /* read disturb, reads per block */

#elif CFG_NAND_TYPE == QLC

#define NAND_TYPE_ID            2
#define NAND_TYPE_NAME          "QLC"
#define NAND_MODEL_CHAR         'Q'
#define NAND_BLOCKS             64
#define NAND_PAGES_PER_BLK      64          /* 16 WL x 4 */
#define NAND_PE_LIMIT           1000
#define NAND_RR_MAX             10
#define NAND_RR_TABLE           { 2, 4, 6, 8, 10, 12, 14, 1, 3, 5 }
#define NAND_RR_REFRESH_LVL     6
#define NAND_RD_LIMIT           8000

#else
#error "unknown CFG_NAND_TYPE"
#endif

#if 0
/* MLC profile (S3 세대) - 더 이상 사용 안함 */
#define NAND_BLOCKS             128
#define NAND_PAGES_PER_BLK      32
#define NAND_PE_LIMIT           10000
#define NAND_RR_MAX             4
#define NAND_RR_TABLE           { 1, 2, 3, 4 }
#endif

#endif /* NAND_PROFILE_H */
