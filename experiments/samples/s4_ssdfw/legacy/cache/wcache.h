/*
 * wcache.h - DRAM write cache (write-back)
 *   2018.02 hwchoi
 */
#ifndef WCACHE_H
#define WCACHE_H

#include "fw_types.h"

void WC_Init(void);
int  WC_Read(u32 u32Lba, u8 *pu8Dst);                       /* 1: hit, 0: miss */
int  WC_Write(u32 u32Lba, const u8 *pu8Src, u32 u32Limit);   /* FTL_OK or error */
int  WC_FlushAll(void);
void WC_Invalidate(u32 u32Lba);
void WC_DropAll(void);
u32  WC_DirtyCount(void);

#endif
