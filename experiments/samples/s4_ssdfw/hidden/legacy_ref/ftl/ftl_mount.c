/*
 * ftl_mount.c - power-on mount / recovery / factory format
 *
 *  1. superblock (blk0, 사본 blk1) 확인.  둘 다 blank 면 factory format
 *  2. meta ring 전체 scan -> 가장 최근의 완전한 checkpoint 선택
 *  3. 그 checkpoint 이후 journal page 를 seq 순서로 replay
 *  4. 마지막 page 가 CLEAN checkpoint 가 아니면 unsafe shutdown
 *  5. valid count / block 상태 재계산, open block 은 모두 닫음
 *  6. boot record (journal) 기록
 *
 *  2016.06 jhkim   initial
 *  2017.03 jhkim   journal replay
 *  2018.09 sypark  fmt 3.0 persist counters
 */
#include "ftl.h"
#include "hal_nand.h"
#include "fw_log.h"
#include "crc32.h"
#include "fw_api.h"

typedef struct {
    uint32_t seq;
    uint32_t base;
    uint16_t part;
    uint16_t nparts;
    uint8_t  type;
    uint8_t  flags;
    uint8_t  ring;
    uint8_t  page;
} mrec_t;

static mrec_t s_rec[META_BLOCKS * FTL_MAX_PPB];
static uint32_t s_nrec;

static void hex8(char *dst, uint32_t v)
{
    static const char hx[] = "0123456789ABCDEF";
    int i;
    for (i = 7; i >= 0; i--) {
        dst[i] = hx[v & 0xF];
        v >>= 4;
    }
}

/* 0: ok, 1: blank, -1: invalid */
static int sb_read_one(uint32_t blk, sb_t *sb)
{
    spare_hdr_t *sp = (spare_hdr_t *)g_ftl_spare;
    int rc;

    rc = ftl_read_page_rr(blk, 0, g_ftl_mbuf, g_ftl_spare);
    if (rc == HAL_NAND_BLANK)
        return 1;
    if (rc != HAL_NAND_OK || !spare_check(sp) || sp->type != PG_TYPE_SB)
        return -1;
    memcpy(sb, g_ftl_mbuf, sizeof(*sb));
    if (sb->magic0 != SB_MAGIC0 || sb->magic1 != SB_MAGIC1)
        return -1;
    if (sb->crc != crc32_calc(sb, offsetof(sb_t, crc)))
        return -1;
    return 0;
}

static int factory_format(void)
{
    sb_t sb;
    uint32_t b, nbad = 0, crc, i;
    char *sn;

    for (b = 0; b < g_ftl.nblk; b++) {
        g_blk[b].ec = 0;
        if (hal_nand_is_bad(b)) {
            g_blk[b].state = BI_BAD_FACTORY;
            nbad++;
        } else {
            g_blk[b].state = (b < SYS_BLOCKS) ? BI_SYSTEM : BI_FREE;
        }
    }
    if (g_blk[SB_BLOCK0].state == BI_BAD_FACTORY || g_blk[SB_BLOCK1].state == BI_BAD_FACTORY)
        return FW_ERR_SUPERBLOCK;
    for (i = 0; i < META_BLOCKS; i++)
        g_ftl.meta_bad[i] = (g_blk[meta_blk(i)].state == BI_BAD_FACTORY);

    g_ftl.capacity = ftl_calc_capacity(g_ftl.pool_blocks, g_ftl.slots_per_blk);
    ftl_calc_spare();

    /* serial = "S4" + type + crc(geometry, bad list) + nblk */
    crc = crc32_update(0xFFFFFFFFu, &g_ftl.nblk, 4);
    crc = crc32_update(crc, &g_ftl.ppb, 4);
    crc = crc32_update(crc, &g_ftl.page_size, 4);
    for (b = 0; b < g_ftl.nblk; b++)
        if (g_blk[b].state == BI_BAD_FACTORY)
            crc = crc32_update(crc, &b, 4);
    crc ^= 0xFFFFFFFFu;

    memset(&sb, 0, sizeof(sb));
    sb.magic0          = SB_MAGIC0;
    sb.magic1          = SB_MAGIC1;
    sb.fmt_version     = FMT_VERSION;
    sb.nand_type       = NAND_TYPE_ID;
    sb.op_percent      = CFG_OP_PERCENT;
    sb.num_blocks      = g_ftl.nblk;
    sb.pages_per_block = g_ftl.ppb;
    sb.page_size       = g_ftl.page_size;
    sb.spare_size      = g_ftl.spare_size;
    sb.sys_blocks      = SYS_BLOCKS;
    sb.meta_start      = META_START;
    sb.meta_blocks     = META_BLOCKS;
    sb.capacity_lbas   = g_ftl.capacity;
    sn = sb.serial;
    memset(sn, ' ', sizeof(sb.serial));
    sn[0] = 'S'; sn[1] = '4'; sn[2] = NAND_MODEL_CHAR;
    hex8(sn + 3, crc);
    sn[11] = (char)('0' + (g_ftl.nblk / 1000) % 10);
    sn[12] = (char)('0' + (g_ftl.nblk / 100) % 10);
    sn[13] = (char)('0' + (g_ftl.nblk / 10) % 10);
    sn[14] = (char)('0' + g_ftl.nblk % 10);
    memcpy(sb.fw_rev, FW_REVISION, 8);
    sb.factory_bad = nbad;
    sb.crc = crc32_calc(&sb, offsetof(sb_t, crc));
    memcpy(g_ftl.serial, sb.serial, sizeof(g_ftl.serial));

    if (sb_write_all(&sb) != 0)
        return FW_ERR_SUPERBLOCK;

    g_ftl.free_cnt = 0;
    for (b = g_ftl.pool_start; b < g_ftl.nblk; b++)
        if (g_blk[b].state == BI_FREE)
            g_ftl.free_cnt++;

    g_ftl.meta_cur = META_BLOCKS - 1;       /* 첫 ckpt 가 ring 0 에 오도록 */
    g_ftl.meta_wp  = g_ftl.ppb;
    g_cnt.user_seq = 1;
    if (ckpt_write(0) != 0)
        return FW_ERR_META;
    LOGI("mount", "factory format done: cap %u lbas, %u bad", g_ftl.capacity, nbad);
    return FW_OK;
}

static void meta_scan(uint32_t *max_seq, uint32_t *cur_ring, uint32_t *used)
{
    spare_hdr_t *sp = (spare_hdr_t *)g_ftl_spare;
    uint32_t r, pg, blk;
    int rc;

    s_nrec = 0;
    *max_seq = 0;
    *cur_ring = 0;
    for (r = 0; r < META_BLOCKS; r++) {
        used[r] = 0;
        blk = meta_blk(r);
        if (hal_nand_is_bad(blk)) {
            g_ftl.meta_bad[r] = 1;
            continue;
        }
        for (pg = 0; pg < g_ftl.ppb; pg++) {
            rc = ftl_read_page_rr(blk, pg, g_ftl_mbuf, g_ftl_spare);
            if (rc == HAL_NAND_BLANK)
                break;
            used[r] = pg + 1;
            if (rc != HAL_NAND_OK)
                continue;               /* torn page (전원 차단 중 program) */
            if (!spare_check(sp))
                continue;
            if (sp->type != PG_TYPE_CKPT && sp->type != PG_TYPE_JRNL)
                continue;
            if (crc32_calc(g_ftl_mbuf, NAND_PAGE_SIZE) != sp->u.m.payload_crc)
                continue;
            s_rec[s_nrec].seq    = sp->seq;
            s_rec[s_nrec].base   = sp->u.m.base_seq;
            s_rec[s_nrec].part   = sp->u.m.part;
            s_rec[s_nrec].nparts = sp->u.m.nparts;
            s_rec[s_nrec].type   = sp->type;
            s_rec[s_nrec].flags  = sp->flags;
            s_rec[s_nrec].ring   = (uint8_t)r;
            s_rec[s_nrec].page   = (uint8_t)pg;
            s_nrec++;
            if (sp->seq > *max_seq) {
                *max_seq = sp->seq;
                *cur_ring = r;
            }
        }
    }
}

static int ckpt_complete(const mrec_t *p0)
{
    uint32_t k, i;
    int found;

    for (k = 1; k < p0->nparts; k++) {
        found = 0;
        for (i = 0; i < s_nrec; i++)
            if (s_rec[i].type == PG_TYPE_CKPT && s_rec[i].base == p0->seq && s_rec[i].part == k)
                found = 1;
        if (!found)
            return 0;
    }
    return 1;
}

static const mrec_t *find_part(uint32_t base, uint32_t part)
{
    uint32_t i;
    for (i = 0; i < s_nrec; i++)
        if (s_rec[i].type == PG_TYPE_CKPT && s_rec[i].base == base && s_rec[i].part == part)
            return &s_rec[i];
    return NULL;
}

static int read_rec(const mrec_t *r)
{
    return ftl_read_page_rr(meta_blk(r->ring), r->page, g_ftl_mbuf, g_ftl_spare);
}

static void replay_page(void)
{
    jrnl_hdr_t *h = (jrnl_hdr_t *)g_ftl_mbuf;
    jrnl_ent_t *e = (jrnl_ent_t *)(g_ftl_mbuf + sizeof(jrnl_hdr_t));
    uint32_t i, blk;

    if (h->magic != JRNL_MAGIC || h->nent > JRNL_MAX_ENTRIES(NAND_PAGE_SIZE))
        return;
    for (i = 0; i < h->nent; i++) {
        if (e[i].key < JK_SPECIAL) {
            if (e[i].key < g_ftl.capacity)
                g_map[e[i].key] = e[i].val;
            continue;
        }
        blk = e[i].key & JK_BLK_MASK;
        if (blk >= g_ftl.nblk)
            continue;
        switch (e[i].key & JK_TYPE_MASK) {
        case JK_ERASE:
            g_blk[blk].ec = e[i].val;
            break;
        case JK_BAD:
            g_blk[blk].state = BI_BAD_GROWN;
            break;
        default:
            break;
        }
    }
    g_cnt = h->p;
}

/* return 0 clean, 1 unsafe, <0 error */
static int meta_load(void)
{
    static uint32_t used[META_BLOCKS];
    const mrec_t *best = NULL, *r;
    ckpt_hdr_t *h = (ckpt_hdr_t *)g_ftl_mbuf;
    ckpt_blk_t *bt = (ckpt_blk_t *)(g_ftl_mbuf + sizeof(ckpt_hdr_t));
    uint32_t max_seq, cur, i, j, k, first, n, last_seq, njr = 0;
    uint32_t best_seq, best_nparts;
    mrec_t tmp;
    int clean;

    meta_scan(&max_seq, &cur, used);

    for (i = 0; i < s_nrec; i++) {
        r = &s_rec[i];
        if (r->type != PG_TYPE_CKPT || r->part != 0 || r->base != r->seq)
            continue;
        if (!ckpt_complete(r))
            continue;
        if (best == NULL || r->seq > best->seq)
            best = r;
    }
    if (best == NULL) {
        LOGE("mount", "no valid checkpoint");
        return FW_ERR_META;
    }

    /* part0: counters + block table */
    if (read_rec(best) != HAL_NAND_OK || h->magic != CKPT_MAGIC ||
        h->capacity != g_ftl.capacity || h->num_blocks != g_ftl.nblk)
        return FW_ERR_META;
    g_cnt = h->p;
    for (i = 0; i < g_ftl.nblk; i++) {
        g_blk[i].ec = bt[i].ec;
        g_blk[i].state = bt[i].state;
    }
    best_seq = best->seq;
    best_nparts = best->nparts;
    last_seq = best_seq;
    clean = (best->flags & SPF_CLEAN) ? 1 : 0;

    /* map parts */
    for (k = 1; k < best_nparts; k++) {
        r = find_part(best_seq, k);
        if (r == NULL || read_rec(r) != HAL_NAND_OK)
            return FW_ERR_META;
        if (r->seq > last_seq)
            last_seq = r->seq;
        first = (k - 1) * MAP_ENTRIES_PER_PAGE;
        n = MIN(MAP_ENTRIES_PER_PAGE, g_ftl.capacity - first);
        memcpy(&g_map[first], g_ftl_mbuf, n * sizeof(uint32_t));
    }

    /* journal pages after the checkpoint, seq order (insertion sort) */
    for (i = 0; i < s_nrec; i++) {
        if (s_rec[i].type != PG_TYPE_JRNL || s_rec[i].base != best_seq || s_rec[i].seq <= last_seq)
            continue;
        s_rec[njr++] = s_rec[i];            /* compact (i >= njr) */
    }
    for (i = 1; i < njr; i++) {
        tmp = s_rec[i];
        for (j = i; j > 0 && s_rec[j - 1].seq > tmp.seq; j--)
            s_rec[j] = s_rec[j - 1];
        s_rec[j] = tmp;
    }
    for (i = 0; i < njr; i++) {
        if (read_rec(&s_rec[i]) != HAL_NAND_OK)
            continue;
        replay_page();
    }
    if (njr > 0 || max_seq > last_seq)
        clean = 0;

    g_ftl.ckpt_base = best_seq;
    g_ftl.meta_seq = max_seq;
    g_ftl.meta_cur = cur;
    g_ftl.meta_wp = used[cur];
    g_ftl.jrnl_pages_since_ckpt = njr;
    LOGI("mount", "ckpt %u, %u journal pages, %s", best_seq, njr, clean ? "clean" : "UNSAFE");
    return clean ? 0 : 1;
}

/* map 으로부터 valid count, block 상태 재구성 */
static void rebuild_state(void)
{
    uint32_t b, lba, m, i;

    for (b = 0; b < g_ftl.nblk; b++) {
        g_blk[b].valid = 0;
        g_blk[b].flags = 0;
        g_blk[b].rd_cnt = 0;
    }
    g_ftl.map_used = 0;
    for (lba = 0; lba < g_ftl.capacity; lba++) {
        m = g_map[lba];
        if (m == MAP_UNMAPPED)
            continue;
        if (MAP_IS_PPA(m) && PPA_BLK(m) >= g_ftl.nblk) {
            g_map[lba] = MAP_UNMAPPED;      /* 깨진 entry */
            continue;
        }
        g_ftl.map_used++;
        if (MAP_IS_PPA(m))
            g_blk[PPA_BLK(m)].valid++;
    }
    g_ftl.free_cnt = 0;
    for (b = g_ftl.pool_start; b < g_ftl.nblk; b++) {
        if (g_blk[b].state == BI_BAD_FACTORY || g_blk[b].state == BI_BAD_GROWN) {
            if (g_blk[b].valid)
                bbm_queue(b);
            continue;
        }
        if (g_blk[b].valid) {
            g_blk[b].state = BI_USED;
        } else {
            g_blk[b].state = BI_FREE;
            g_ftl.free_cnt++;
        }
    }
    for (i = 0; i < META_BLOCKS; i++) {
        b = meta_blk(i);
        if (g_blk[b].state == BI_BAD_FACTORY || g_blk[b].state == BI_BAD_GROWN)
            g_ftl.meta_bad[i] = 1;
    }
}

int ftl_mount(void)
{
    sb_t sb;
    int rc0, rc1, rc, clean = 1;

    if (ftl_geometry_setup() != 0)
        return FW_ERR_GEOMETRY;

    rc0 = sb_read_one(SB_BLOCK0, &sb);
    rc1 = (rc0 == 0) ? 0 : sb_read_one(SB_BLOCK1, &sb);

    if (rc0 == 1 && rc1 == 1) {
        rc = factory_format();
        if (rc != FW_OK)
            return rc;
    } else {
        if (rc0 != 0 && rc1 != 0)
            return FW_ERR_SUPERBLOCK;
        if ((sb.fmt_version >> 8) != FMT_VERSION_MAJOR) {
            LOGE("mount", "format version %04x not supported", sb.fmt_version);
            return FW_ERR_VERSION;
        }
        if (sb.nand_type != NAND_TYPE_ID) {
            LOGE("mount", "NAND type mismatch (drive %u, fw %u)", sb.nand_type, NAND_TYPE_ID);
            return FW_ERR_NAND_TYPE;
        }
        if (sb.num_blocks != g_ftl.nblk || sb.pages_per_block != g_ftl.ppb ||
            sb.capacity_lbas > FTL_MAX_LBAS)
            return FW_ERR_GEOMETRY;
        g_ftl.capacity = sb.capacity_lbas;
        memcpy(g_ftl.serial, sb.serial, sizeof(g_ftl.serial));
        ftl_calc_spare();

        rc = meta_load();
        if (rc < 0)
            return rc;
        clean = (rc == 0);
        rebuild_state();
    }

    if (!clean)
        g_cnt.unsafe_shutdowns++;
    g_cnt.power_cycles++;
    jrnl_commit(1, SPF_BOOT);
    return FW_OK;
}
