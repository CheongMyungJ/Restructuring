/*
 * ftl_alloc.c - block allocation / erase / stream page program
 *
 * free block 은 할당 시점에 erase 한다 (erase-on-allocate).
 * 할당 정책: free block 중 erase count 최소, 같으면 block 번호 작은 것.
 *
 *  2016.06 jhkim   initial
 *  2017.05 sypark  erase 전에 journal commit (전원 차단 시 old data 참조 방지)
 *  2018.04 dykang  program fail -> retire
 */
#include "ftl.h"
#include "hal_nand.h"
#include "fw_log.h"
#include "crc32.h"

static uint8_t s_spare_w[FTL_MAX_SPARE];

/* used block 이 모두 invalid 가 되면 free 로 돌린다 (open block 제외) */
void ftl_check_free(uint32_t blk)
{
    if (blk >= g_ftl.nblk)
        return;
    if (g_blk[blk].state != BI_USED || g_blk[blk].valid != 0)
        return;
    if (ftl_is_open(blk))
        return;
    g_blk[blk].state = BI_FREE;
    g_ftl.free_cnt++;
}

int ftl_erase_block(uint32_t blk)
{
    int rc;

    /* map 변경이 journal 에 남아 있으면 먼저 commit - erase 후 전원이 나가면
     * old map 이 지워진 block 을 가리키게 됨 (2017.05 field issue #1187) */
    if (g_ftl.jrnl_map_dirty)
        jrnl_commit(0, 0);

    rc = hal_nand_erase(blk);
    g_blk[blk].rd_cnt = 0;
    refresh_cancel(blk);
    if (rc != HAL_NAND_OK) {
        LOGE("alloc", "erase fail blk %u rc %d", blk, rc);
        g_cnt.erase_fail_count++;
        bbm_retire(blk, BAD_ERASE_FAIL);
        return -1;
    }
    g_blk[blk].ec++;
    jrnl_add(JK_ERASE | blk, g_blk[blk].ec);
    return 0;
}

uint32_t ftl_alloc_block(int st)
{
    uint32_t b, best, n = 0;

    /* foreground GC (host stream only)
     * free 가 2 이상이면 GC_FG_MAX_LOOP 회까지만 (spare 부족 시 무한 GC 방지, #1733) */
    if (st == STREAM_HOST && !g_ftl.in_gc) {
        while (g_ftl.free_cnt < GC_FG_THRESHOLD) {
            if (g_ftl.free_cnt >= 2 && n >= GC_FG_MAX_LOOP)
                break;
            if (gc_run_one(GC_FOREGROUND) <= 0)
                break;
            n++;
        }
    }

    for (;;) {
        best = BLK_NONE;
        for (b = g_ftl.pool_start; b < g_ftl.nblk; b++) {
            if (g_blk[b].state != BI_FREE)
                continue;
            if (best == BLK_NONE || g_blk[b].ec < g_blk[best].ec)
                best = b;
        }
        if (best == BLK_NONE) {
            LOGE("alloc", "no free block (stream %d)", st);
            return BLK_NONE;
        }
        if (ftl_erase_block(best) == 0)
            break;
        /* erase fail: block retired, try next one */
    }

    g_blk[best].state = BI_USED;
    g_blk[best].valid = 0;
    g_blk[best].last_seq = g_cnt.user_seq;
    if (g_ftl.free_cnt)
        g_ftl.free_cnt--;
    LOGT("alloc", "alloc blk %u ec %u st %d free %u", best, g_blk[best].ec, st, g_ftl.free_cnt);
    return best;
}

void ftl_close_stream(int st)
{
    stream_t *s = &g_ftl.st[st];
    uint32_t b = s->open_blk;

    if (b == BLK_NONE)
        return;
    s->open_blk = BLK_NONE;
    s->wp = 0;
    ftl_check_free(b);
}

/*
 * stream page buffer 를 open block 에 program.
 * program fail 시 block retire 후 새 block 에 같은 page 를 다시 기록한다.
 * (fail 난 block 의 기존 data 는 retire queue 에서 나중에 relocation)
 */
int ftl_program_stream_page(int st)
{
    stream_t *s = &g_ftl.st[st];
    spare_hdr_t *sp = (spare_hdr_t *)s_spare_w;
    uint32_t i, b;
    int rc;

    for (;;) {
        if (s->open_blk == BLK_NONE) {
            s->open_blk = ftl_alloc_block(st);
            s->wp = 0;
            if (s->open_blk == BLK_NONE)
                return FTL_ERR_NOSPACE;
        }
        memset(s_spare_w, 0xFF, sizeof(s_spare_w));
        spare_build(sp, PG_TYPE_USER, 0, g_cnt.user_seq);
        for (i = 0; i < SLOTS_PER_PAGE; i++)
            sp->u.lba[i] = s->lba[i];
        spare_seal(sp);

        rc = hal_nand_program(s->open_blk, s->wp, s->buf, s_spare_w);
        g_cnt.nand_data_programs++;
        if (rc == HAL_NAND_OK)
            break;

        LOGE("alloc", "program fail blk %u page %u rc %d", s->open_blk, s->wp, rc);
        g_cnt.prog_fail_count++;
        b = s->open_blk;
        s->open_blk = BLK_NONE;
        s->wp = 0;
        bbm_retire(b, BAD_PROG_FAIL);
    }

    g_cnt.user_seq++;
    b = s->open_blk;
    for (i = 0; i < SLOTS_PER_PAGE; i++) {
        if (s->lba[i] == INVALID_U32)
            continue;
        ftl_map_set(s->lba[i], PPA_MAKE(b, s->wp, i));
    }
    g_blk[b].last_seq = g_cnt.user_seq;
    s->wp++;
    s->nslot = 0;
    if (s->wp >= g_ftl.ppb)
        ftl_close_stream(st);
    return FTL_OK;
}
