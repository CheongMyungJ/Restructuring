/*
 * ftl_meta.c - metadata persistence (checkpoint + journal), superblock write
 *
 * meta 영역: block META_START .. META_START+META_BLOCKS-1 를 ring 으로 사용.
 *  - 새 meta block 으로 넘어갈 때는 항상 checkpoint 를 먼저 기록
 *    (그래서 가장 오래된 block 을 지워도 최신 checkpoint 는 남는다)
 *  - checkpoint = part0 (header + persist counters + block table)
 *                 + part1..n (map, 4096 entry/page)
 *  - journal page = persist counters snapshot + map/erase/bad entries
 *
 *  2017.03 jhkim   initial (fmt 2.0)
 *  2018.09 sypark  persist counters (fmt 3.0)
 */
#include "ftl.h"
#include "hal_nand.h"
#include "fw_log.h"
#include "crc32.h"

static uint8_t s_jbuf[NAND_PAGE_SIZE];          /* journal page under construction */
static uint8_t s_mspare[FTL_MAX_SPARE];

#define JRNL_ENT(i)     (((jrnl_ent_t *)(s_jbuf + sizeof(jrnl_hdr_t)))[i])

uint32_t meta_blk(uint32_t ring_idx)
{
    return META_START + ring_idx;
}

void spare_build(spare_hdr_t *sp, uint8_t type, uint8_t flags, uint32_t seq)
{
    memset(sp, 0, sizeof(*sp));
    sp->magic = SPARE_MAGIC;
    sp->type  = type;
    sp->flags = flags;
    sp->seq   = seq;
}

void spare_seal(spare_hdr_t *sp)
{
    sp->crc = crc32_calc(sp, SPARE_HDR_CRC_LEN);
}

int spare_check(const spare_hdr_t *sp)
{
    if (sp->magic != SPARE_MAGIC)
        return 0;
    return sp->crc == crc32_calc(sp, SPARE_HDR_CRC_LEN);
}

void jrnl_reset(void)
{
    memset(s_jbuf, 0, sizeof(s_jbuf));
    g_ftl.jrnl_nent = 0;
    g_ftl.jrnl_map_dirty = 0;
}

void jrnl_add(uint32_t key, uint32_t val)
{
    if (g_ftl.jrnl_nent >= JRNL_MAX_ENTRIES(NAND_PAGE_SIZE))
        jrnl_commit(1, 0);
    JRNL_ENT(g_ftl.jrnl_nent).key = key;
    JRNL_ENT(g_ftl.jrnl_nent).val = val;
    g_ftl.jrnl_nent++;
    if (key < JK_SPECIAL)
        g_ftl.jrnl_map_dirty = 1;
}

/* 현재 meta block 에 한 page program. fail 이면 meta block retire */
static int meta_program(const uint8_t *data, const spare_hdr_t *sp)
{
    uint32_t blk = meta_blk(g_ftl.meta_cur);
    int rc;

    memset(s_mspare, 0xFF, sizeof(s_mspare));
    memcpy(s_mspare, sp, sizeof(*sp));
    rc = hal_nand_program(blk, g_ftl.meta_wp, data, s_mspare);
    g_ftl.meta_wp++;
    if (rc != HAL_NAND_OK) {
        LOGE("meta", "meta program fail blk %u pg %u", blk, g_ftl.meta_wp - 1);
        g_ftl.meta_bad[g_ftl.meta_cur] = 1;
        if (g_blk[blk].state != BI_BAD_GROWN) {
            g_blk[blk].state = BI_BAD_GROWN;
            g_cnt.prog_fail_count++;
            g_cnt.grown_bad_count++;
        }
        return -1;
    }
    return 0;
}

/* ring 의 다음 good meta block 으로 이동 (erase) */
static int meta_next_block(void)
{
    uint32_t i, idx, blk;
    int rc;

    for (i = 0; i < META_BLOCKS; i++) {
        idx = (g_ftl.meta_cur + 1 + i) % META_BLOCKS;
        if (g_ftl.meta_bad[idx])
            continue;
        blk = meta_blk(idx);
        rc = hal_nand_erase(blk);
        if (rc != HAL_NAND_OK) {
            LOGE("meta", "meta erase fail blk %u", blk);
            g_ftl.meta_bad[idx] = 1;
            g_blk[blk].state = BI_BAD_GROWN;
            g_cnt.erase_fail_count++;
            g_cnt.grown_bad_count++;
            continue;
        }
        g_blk[blk].ec++;
        g_ftl.meta_cur = idx;
        g_ftl.meta_wp = 0;
        return 0;
    }
    LOGE("meta", "no usable meta block!");
    return -1;
}

static int ckpt_write_parts(uint8_t flags, uint32_t nparts)
{
    ckpt_hdr_t  *h = (ckpt_hdr_t *)g_ftl_mbuf;
    ckpt_blk_t  *bt = (ckpt_blk_t *)(g_ftl_mbuf + sizeof(ckpt_hdr_t));
    spare_hdr_t  sp;
    uint32_t     base = g_ftl.meta_seq + 1;
    uint32_t     part, b, first, n;

    for (part = 0; part < nparts; part++) {
        memset(g_ftl_mbuf, 0, NAND_PAGE_SIZE);
        if (part == 0) {
            h->magic       = CKPT_MAGIC;
            h->fmt_version = FMT_VERSION;
            h->nparts      = (uint16_t)nparts;
            h->capacity    = g_ftl.capacity;
            h->num_blocks  = g_ftl.nblk;
            h->p           = g_cnt;
            for (b = 0; b < g_ftl.nblk; b++) {
                bt[b].ec    = g_blk[b].ec;
                bt[b].state = g_blk[b].state;
            }
        } else {
            first = (part - 1) * MAP_ENTRIES_PER_PAGE;
            n = MIN(MAP_ENTRIES_PER_PAGE, g_ftl.capacity - first);
            memset(g_ftl_mbuf, 0xFF, NAND_PAGE_SIZE);
            memcpy(g_ftl_mbuf, &g_map[first], n * sizeof(uint32_t));
        }
        spare_build(&sp, PG_TYPE_CKPT, flags, ++g_ftl.meta_seq);
        sp.u.m.base_seq    = base;
        sp.u.m.part        = (uint16_t)part;
        sp.u.m.nparts      = (uint16_t)nparts;
        sp.u.m.count       = g_ftl.capacity;
        sp.u.m.payload_crc = crc32_calc(g_ftl_mbuf, NAND_PAGE_SIZE);
        spare_seal(&sp);
        if (meta_program(g_ftl_mbuf, &sp) != 0)
            return -1;
    }
    g_ftl.ckpt_base = base;
    return 0;
}

int ckpt_write(uint8_t flags)
{
    uint32_t nparts = 1 + DIV_ROUND_UP(g_ftl.capacity, MAP_ENTRIES_PER_PAGE);
    uint32_t tries;
    int need_new = 0;

    g_cnt.ckpt_count++;
    for (tries = 0; tries < META_BLOCKS; tries++) {
        if (need_new || g_ftl.meta_bad[g_ftl.meta_cur] ||
            g_ftl.meta_wp + nparts > g_ftl.ppb) {
            if (meta_next_block() != 0)
                return -1;
        }
        if (ckpt_write_parts(flags, nparts) == 0) {
            jrnl_reset();
            g_ftl.writes_since_ckpt = 0;
            g_ftl.jrnl_pages_since_ckpt = 0;
            LOGI("meta", "ckpt base %u flags %x blk %u", g_ftl.ckpt_base, flags,
                 meta_blk(g_ftl.meta_cur));
            return 0;
        }
        need_new = 1;
    }
    return -1;
}

/*
 * journal page 기록.  force=0 이면 entry 가 있을 때만.
 * meta block 이 꽉 찼으면 checkpoint 로 대체 (journal 내용 흡수).
 */
int jrnl_commit(int force, uint8_t flags)
{
    jrnl_hdr_t *h = (jrnl_hdr_t *)s_jbuf;
    spare_hdr_t sp;

    if (!force && g_ftl.jrnl_nent == 0)
        return 0;
    if (g_ftl.meta_bad[g_ftl.meta_cur] || g_ftl.meta_wp >= g_ftl.ppb)
        return ckpt_write(0);

    h->magic = JRNL_MAGIC;
    h->nent  = g_ftl.jrnl_nent;
    h->p     = g_cnt;
    spare_build(&sp, PG_TYPE_JRNL, flags, ++g_ftl.meta_seq);
    sp.u.m.base_seq    = g_ftl.ckpt_base;
    sp.u.m.part        = 0;
    sp.u.m.nparts      = 1;
    sp.u.m.count       = g_ftl.jrnl_nent;
    sp.u.m.payload_crc = crc32_calc(s_jbuf, NAND_PAGE_SIZE);
    spare_seal(&sp);

    if (meta_program(s_jbuf, &sp) != 0)
        return ckpt_write(0);

    jrnl_reset();
    g_ftl.jrnl_pages_since_ckpt++;
    return 0;
}

/* command 처리 후 호출 - checkpoint 주기 */
void ftl_meta_after_cmd(void)
{
    if (g_ftl.writes_since_ckpt >= CKPT_INTERVAL ||
        g_ftl.jrnl_pages_since_ckpt >= JRNL_MAX_PAGES)
        (void)ckpt_write(0);
}

/* superblock 을 block 0, 1 page 0 에 기록 */
int sb_write_all(const sb_t *sb)
{
    spare_hdr_t sp;
    uint32_t i, blk;
    int ok = 0;

    for (i = 0; i < 2; i++) {
        blk = (i == 0) ? SB_BLOCK0 : SB_BLOCK1;
        if (hal_nand_erase(blk) != HAL_NAND_OK) {
            LOGE("meta", "sb erase fail blk %u", blk);
            continue;
        }
        g_blk[blk].ec++;
        memset(g_ftl_mbuf, 0, NAND_PAGE_SIZE);
        memcpy(g_ftl_mbuf, sb, sizeof(*sb));
        spare_build(&sp, PG_TYPE_SB, 0, 0);
        sp.u.m.payload_crc = crc32_calc(g_ftl_mbuf, NAND_PAGE_SIZE);
        spare_seal(&sp);
        memset(s_mspare, 0xFF, sizeof(s_mspare));
        memcpy(s_mspare, &sp, sizeof(sp));
        if (hal_nand_program(blk, 0, g_ftl_mbuf, s_mspare) == HAL_NAND_OK)
            ok++;
    }
    return ok ? 0 : -1;
}
