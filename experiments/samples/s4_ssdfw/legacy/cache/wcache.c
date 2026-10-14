/*
 * wcache.c - DRAM write cache
 *
 * - 4KiB entry x CACHE_ENTRIES, write-back
 * - 같은 LBA 재기록 시 entry 덮어씀 (순서 유지)
 * - 가득 차면 가장 오래된 entry CACHE_DESTAGE_BATCH 개를 NAND 로 destage
 * - destage 후 남는 partial page 는 padding 해서 program (FTL page buffer 에
 *   데이터를 남기지 않는다 -> read path 단순화)
 * - read 는 cache 를 먼저 확인
 *
 *  2018.02 hwchoi  initial (S3 의 read cache 제거, write cache 로 단순화)
 *  2018.11 mjlee   thermal limit (u32Limit) 추가
 */
#include "wcache.h"
#include "fw_config.h"
#include "ftl.h"
#include "fw_log.h"

typedef struct {
    u32 u32Lba;
    u32 u32Seq;         /* insert order */
    u8  u8Valid;
    u8  au8Rsvd[3];
} WC_ENTRY;

static WC_ENTRY g_astWcEnt[CACHE_ENTRIES];
static u8       g_au8WcData[CACHE_ENTRIES][LBA_SIZE];
static u32      g_u32WcSeq;
static u32      g_u32WcDirty;

void WC_Init(void)
{
    memset(g_astWcEnt, 0, sizeof(g_astWcEnt));
    g_u32WcSeq = 0;
    g_u32WcDirty = 0;
}

static int WC_Lookup(u32 u32Lba)
{
    int i;

    for (i = 0; i < CACHE_ENTRIES; i++) {
        if (g_astWcEnt[i].u8Valid && g_astWcEnt[i].u32Lba == u32Lba)
            return i;
    }
    return -1;
}

static int WC_FindFree(void)
{
    int i;

    for (i = 0; i < CACHE_ENTRIES; i++)
        if (!g_astWcEnt[i].u8Valid)
            return i;
    return -1;
}

static int WC_FindOldest(void)
{
    int i, iOld = -1;

    for (i = 0; i < CACHE_ENTRIES; i++) {
        if (!g_astWcEnt[i].u8Valid)
            continue;
        if (iOld < 0 || g_astWcEnt[i].u32Seq < g_astWcEnt[iOld].u32Seq)
            iOld = i;
    }
    return iOld;
}

/* oldest u32Cnt entries -> NAND */
static int WC_Destage(u32 u32Cnt)
{
    u32 i;
    int iIdx, iRet = FTL_OK, iRc;

    for (i = 0; i < u32Cnt; i++) {
        iIdx = WC_FindOldest();
        if (iIdx < 0)
            break;
        iRc = ftl_write_lba(STREAM_HOST, g_astWcEnt[iIdx].u32Lba, g_au8WcData[iIdx]);
        if (iRc != FTL_OK)
            iRet = iRc;
        g_astWcEnt[iIdx].u8Valid = 0;
        g_u32WcDirty--;
    }
    iRc = ftl_flush_stream(STREAM_HOST);
    if (iRc != FTL_OK)
        iRet = iRc;
    return iRet;
}

int WC_Read(u32 u32Lba, u8 *pu8Dst)
{
    int iIdx = WC_Lookup(u32Lba);

    if (iIdx < 0)
        return 0;
    memcpy(pu8Dst, g_au8WcData[iIdx], LBA_SIZE);
    return 1;
}

int WC_Write(u32 u32Lba, const u8 *pu8Src, u32 u32Limit)
{
    int iIdx, iRc = FTL_OK;

    iIdx = WC_Lookup(u32Lba);
    if (iIdx >= 0) {
        memcpy(g_au8WcData[iIdx], pu8Src, LBA_SIZE);   /* overwrite, keep order */
        return FTL_OK;
    }
    if (u32Limit > CACHE_ENTRIES)
        u32Limit = CACHE_ENTRIES;
    if (g_u32WcDirty >= u32Limit)
        iRc = WC_Destage(CACHE_DESTAGE_BATCH);

    iIdx = WC_FindFree();
    if (iIdx < 0) {                     /* 있으면 안됨 */
        LOGE("wc", "no free entry (dirty %u)", g_u32WcDirty);
        return FTL_ERR_NOSPACE;
    }
    g_astWcEnt[iIdx].u32Lba = u32Lba;
    g_astWcEnt[iIdx].u32Seq = g_u32WcSeq++;
    g_astWcEnt[iIdx].u8Valid = 1;
    memcpy(g_au8WcData[iIdx], pu8Src, LBA_SIZE);
    g_u32WcDirty++;
    return iRc;
}

int WC_FlushAll(void)
{
    if (g_u32WcDirty == 0)
        return FTL_OK;
    return WC_Destage(g_u32WcDirty);
}

void WC_Invalidate(u32 u32Lba)
{
    int iIdx = WC_Lookup(u32Lba);

    if (iIdx < 0)
        return;
    g_astWcEnt[iIdx].u8Valid = 0;
    g_u32WcDirty--;
}

void WC_DropAll(void)
{
    WC_Init();
}

u32 WC_DirtyCount(void)
{
    return g_u32WcDirty;
}
