/* t_common.c - hidden harness helpers */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include "t_common.h"

uint32_t g_cap;
jmp_buf  g_cut_jmp;

static uint32_t s_rs = 1;
static uint8_t  s_io[MDTS * BLK];

/* model */
static uint32_t m_curv[MAXLBA], m_durv[MAXLBA], m_minv[MAXLBA], m_maxv[MAXLBA];
static uint8_t  m_trim_since[MAXLBA];
static uint32_t m_inj[MAXLBA][3];
static uint32_t m_next = 1;
static int      m_wt;

void out(const char *key, const char *fmt, ...)
{
    va_list ap;
    printf("R %s ", key);
    va_start(ap, fmt);
    vprintf(fmt, ap);
    va_end(ap);
    printf("\n");
    fflush(stdout);
}

void rnd_seed(uint32_t s) { s_rs = s ? s : 1; }
uint32_t rnd(void)
{
    s_rs ^= s_rs << 13; s_rs ^= s_rs >> 17; s_rs ^= s_rs << 5;
    return s_rs;
}

static uint16_t submit(uint16_t sqid, uint8_t opc, uint32_t nsid, uint64_t slba, uint32_t nlb,
                       uint32_t c10, uint32_t c11, uint32_t c12, void *buf, uint32_t *cdw0)
{
    nvme_cmd_t c;
    nvme_cpl_t r;
    memset(&c, 0, sizeof(c));
    memset(&r, 0, sizeof(r));
    c.sqid = sqid; c.cid = 0x77; c.opcode = opc; c.nsid = nsid; c.slba = slba; c.nlb = nlb;
    c.cdw10 = c10; c.cdw11 = c11; c.cdw12 = c12;
    if (sqid) {
        c.cdw10 = c10 ? c10 : (uint32_t)slba;
        c.cdw11 = c11 ? c11 : (uint32_t)(slba >> 32);
        c.cdw12 = c12 | (nlb & 0xFFFF);
    }
    fw_submit(&c, buf, &r);
    if (cdw0)
        *cdw0 = r.cdw0;
    return r.status;
}

uint16_t io_cmd(uint8_t opc, uint32_t nsid, uint64_t slba, uint32_t nlb,
                uint32_t c10, uint32_t c11, uint32_t c12, void *buf, uint32_t *cdw0)
{
    return submit(1, opc, nsid, slba, nlb, c10, c11, c12, buf, cdw0);
}

uint16_t adm_cmd(uint8_t opc, uint32_t nsid, uint32_t c10, uint32_t c11, void *buf, uint32_t *cdw0)
{
    return submit(0, opc, nsid, 0, 0, c10, c11, 0, buf, cdw0);
}

int boot(void)
{
    uint8_t id[4096];
    int rc = fw_init();
    g_cap = 0;
    if (rc == 0 && adm_cmd(0x06, 1, 0, 0, id, NULL) == 0) {
        memcpy(&g_cap, id, 4);
        if (g_cap > MAXLBA)
            g_cap = MAXLBA;
    }
    return rc;
}

void tick(uint32_t ms)
{
    hsim_advance(ms);
    fw_tick(ms);
}

void cut_handler(void)
{
    hsim_disarm_cut();
    longjmp(g_cut_jmp, 1);
}

void make_block(uint8_t *p, uint32_t lba, uint32_t ver, uint32_t it, uint32_t ip, uint32_t id)
{
    uint32_t i, x = lba * 2654435761u ^ ver * 40503u ^ 0x9E3779B9u;
    if (ver == 0) {
        memset(p, 0, BLK);
        return;
    }
    memcpy(p, "TDAT", 4);
    memcpy(p + 4, &lba, 4);
    memcpy(p + 8, &ver, 4);
    memset(p + 12, 0, 20);
    if (it) {
        memcpy(p + 16, "@INJ", 4);
        memcpy(p + 20, &it, 4);
        memcpy(p + 24, &ip, 4);
        memcpy(p + 28, &id, 4);
    }
    for (i = 32; i < BLK; i += 4) {
        x ^= x << 13; x ^= x >> 17; x ^= x << 5;
        memcpy(p + i, &x, 4);
    }
}

int64_t block_ver(const uint8_t *p, uint32_t lba)
{
    static uint8_t exp[BLK];
    uint32_t l, v, it, ip, id, i;
    for (i = 0; i < BLK && p[i] == 0; i++)
        ;
    if (i == BLK)
        return 0;
    if (memcmp(p, "TDAT", 4) != 0)
        return -1;
    memcpy(&l, p + 4, 4);
    memcpy(&v, p + 8, 4);
    if (l != lba || v == 0)
        return -1;
    it = ip = id = 0;
    if (memcmp(p + 16, "@INJ", 4) == 0) {
        memcpy(&it, p + 20, 4); memcpy(&ip, p + 24, 4); memcpy(&id, p + 28, 4);
    }
    make_block(exp, lba, v, it, ip, id);
    return memcmp(exp, p, BLK) == 0 ? (int64_t)v : -1;
}

void m_reset(void)
{
    memset(m_curv, 0, sizeof(m_curv));
    memset(m_durv, 0, sizeof(m_durv));
    memset(m_minv, 0, sizeof(m_minv));
    memset(m_maxv, 0, sizeof(m_maxv));
    memset(m_trim_since, 0, sizeof(m_trim_since));
    memset(m_inj, 0, sizeof(m_inj));
    m_next = 1;
    m_wt = 0;
}

void m_set_wt(int wt) { m_wt = wt; }
uint32_t m_cur(uint32_t lba) { return m_curv[lba]; }

static void m_mark_volatile(uint32_t lba, uint32_t v)
{
    m_curv[lba] = v;
    if (!m_minv[lba] || v < m_minv[lba])
        m_minv[lba] = v;
    if (v > m_maxv[lba])
        m_maxv[lba] = v;
}

static void m_mark_durable(uint32_t lba)
{
    m_durv[lba] = m_curv[lba];
    m_minv[lba] = m_maxv[lba] = 0;
    m_trim_since[lba] = 0;
}

static uint16_t m_write_ex(uint64_t slba, uint32_t n, int fua, const uint32_t *inj)
{
    uint32_t i, v = m_next++;
    uint16_t st;
    for (i = 0; i < n; i++) {
        make_block(s_io + (size_t)i * BLK, (uint32_t)(slba + i), v,
                   inj ? inj[0] : 0, inj ? inj[1] : 0, inj ? inj[2] : 0);
        m_inj[slba + i][0] = inj ? inj[0] : 0;
        m_inj[slba + i][1] = inj ? inj[1] : 0;
        m_inj[slba + i][2] = inj ? inj[2] : 0;
        m_mark_volatile((uint32_t)(slba + i), v);
    }
    st = io_cmd(0x01, 1, slba, n - 1, 0, 0, fua ? (1u << 30) : 0, s_io, NULL);
    if (st == 0 && (fua || m_wt))
        for (i = 0; i < n; i++)
            m_mark_durable((uint32_t)(slba + i));
    return st;
}

uint16_t m_write(uint64_t slba, uint32_t n, int fua)
{
    uint32_t c;
    uint16_t st = 0, s;
    while (n) {
        c = n > MDTS ? MDTS : n;
        s = m_write_ex(slba, c, fua, NULL);
        if (s) st = s;
        slba += c;
        n -= c;
    }
    return st;
}

uint16_t m_write_inj(uint32_t lba, uint32_t type, uint32_t param, uint32_t id)
{
    uint32_t inj[3] = { type, param, id };
    return m_write_ex(lba, 1, 0, inj);
}

uint16_t m_flush(void)
{
    uint32_t i;
    uint16_t st = io_cmd(0x00, 1, 0, 0, 0, 0, 0, NULL, NULL);
    if (st == 0)
        for (i = 0; i < MAXLBA; i++)
            m_mark_durable(i);
    return st;
}

uint16_t m_trim(uint64_t slba, uint32_t n)
{
    uint8_t r[16];
    uint32_t i;
    memset(r, 0, sizeof(r));
    memcpy(r + 4, &n, 4);
    memcpy(r + 8, &slba, 8);
    for (i = 0; i < n; i++) {
        m_curv[slba + i] = 0;
        m_trim_since[slba + i] = 1;
    }
    return io_cmd(0x09, 1, 0, 0, 0, 4, 0, r, NULL);
}

void m_format(void)
{
    uint32_t i;
    for (i = 0; i < MAXLBA; i++) {
        m_curv[i] = 0;
        m_trim_since[i] = 1;
    }
}

int64_t m_read_ver(uint32_t lba, uint16_t *st)
{
    uint16_t s = io_cmd(0x02, 1, lba, 0, 0, 0, 0, s_io, NULL);
    if (st) *st = s;
    if (s)
        return -2;
    return block_ver(s_io, lba);
}

uint32_t m_verify_exact(uint32_t lo, uint32_t hi)
{
    uint32_t lba, c, i, bad = 0;
    uint16_t st;
    for (lba = lo; lba < hi; lba += c) {
        c = (hi - lba) > MDTS ? MDTS : (hi - lba);
        st = io_cmd(0x02, 1, lba, c - 1, 0, 0, 0, s_io, NULL);
        for (i = 0; i < c; i++)
            if (st || block_ver(s_io + (size_t)i * BLK, lba + i) != (int64_t)m_curv[lba + i])
                bad++;
    }
    return bad;
}

uint32_t m_verify_durable(uint32_t lo, uint32_t hi)
{
    uint32_t lba, c, i, l, bad = 0;
    uint16_t st;
    int64_t v;
    int ok;
    for (lba = lo; lba < hi; lba += c) {
        c = (hi - lba) > MDTS ? MDTS : (hi - lba);
        st = io_cmd(0x02, 1, lba, c - 1, 0, 0, 0, s_io, NULL);
        for (i = 0; i < c; i++) {
            l = lba + i;
            v = st ? -2 : block_ver(s_io + (size_t)i * BLK, l);
            ok = (v == (int64_t)m_durv[l]) ||
                 (v > 0 && m_minv[l] && v >= m_minv[l] && v <= m_maxv[l]) ||
                 (v == 0 && m_trim_since[l]);
            if (!ok) {
                bad++;
                continue;
            }
            m_curv[l] = (uint32_t)v;    /* adopt recovered state */
            m_mark_durable(l);
        }
    }
    return bad;
}

int m_save(const char *path, const uint64_t *extra, int nextra)
{
    FILE *f = fopen(path, "wb");
    if (!f) return -1;
    fwrite(m_curv, sizeof(m_curv), 1, f);
    fwrite(m_durv, sizeof(m_durv), 1, f);
    fwrite(m_minv, sizeof(m_minv), 1, f);
    fwrite(m_maxv, sizeof(m_maxv), 1, f);
    fwrite(m_trim_since, sizeof(m_trim_since), 1, f);
    fwrite(&m_next, 4, 1, f);
    fwrite(extra, 8, (size_t)nextra, f);
    return fclose(f);
}

int m_load(const char *path, uint64_t *extra, int nextra)
{
    FILE *f = fopen(path, "rb");
    int ok = 1;
    if (!f) return -1;
    ok &= fread(m_curv, sizeof(m_curv), 1, f) == 1;
    ok &= fread(m_durv, sizeof(m_durv), 1, f) == 1;
    ok &= fread(m_minv, sizeof(m_minv), 1, f) == 1;
    ok &= fread(m_maxv, sizeof(m_maxv), 1, f) == 1;
    ok &= fread(m_trim_since, sizeof(m_trim_since), 1, f) == 1;
    ok &= fread(&m_next, 4, 1, f) == 1;
    ok &= fread(extra, 8, (size_t)nextra, f) == (size_t)nextra;
    fclose(f);
    return ok ? 0 : -2;
}

static uint64_t le(const uint8_t *p, int n)
{
    uint64_t v = 0;
    while (n--)
        v = (v << 8) | p[n];
    return v;
}

int smart_get(smart_t *s)
{
    memset(s, 0, sizeof(*s));
    s->st = adm_cmd(0x02, 0xFFFFFFFFu, 0x02 | (127u << 16), 0, s->raw, NULL);
    s->cw = s->raw[0]; s->temp = (uint16_t)le(s->raw + 1, 2);
    s->spare = s->raw[3]; s->thr = s->raw[4]; s->used = s->raw[5];
    s->dur = le(s->raw + 32, 8);  s->duw = le(s->raw + 48, 8);
    s->rcmd = le(s->raw + 64, 8); s->wcmd = le(s->raw + 80, 8);
    s->pc = le(s->raw + 112, 8);  s->poh = le(s->raw + 128, 8);
    s->unsafe = le(s->raw + 144, 8); s->media = le(s->raw + 160, 8);
    s->errlog = le(s->raw + 176, 8);
    return s->st;
}

int c0_get(c0_t *c)
{
    int i;
    memset(c, 0, sizeof(*c));
    c->st = adm_cmd(0xC0, 0, 0, 0, c->raw, &c->cdw0);
    for (i = 0; i < 23; i++)
        c->f[i] = ((uint32_t)c->raw[i * 4] << 24) | ((uint32_t)c->raw[i * 4 + 1] << 16) |
                  ((uint32_t)c->raw[i * 4 + 2] << 8) | c->raw[i * 4 + 3];
    return c->st;
}
