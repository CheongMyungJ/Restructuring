/* t_ssd.c - hidden harness scenarios (part 1) + main
 * usage: t_ssd <scenario> [--in img] [--out img] [--state f] [--tag t] [--mode m] [--n N]
 * prints "R <key> <value>" lines */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "t_common.h"

const char *a_in, *a_out, *a_state, *a_tag = "x", *a_mode = "clean";
uint32_t a_n;

static const uint32_t BAD2[2] = { 37, 61 };
static uint8_t buf[MDTS * BLK];

static void fresh(const uint32_t *bad, int nbad)
{
    hsim_reset(bad, nbad);
    m_reset();
    out("init", "%d", boot());
}

static void hex(char *dst, const uint8_t *p, int n)
{
    int i;
    for (i = 0; i < n; i++)
        sprintf(dst + i * 2, "%02x", p[i]);
}

static void sc_cmd(void)
{
    uint32_t cap, cdw0 = 0, i;
    uint8_t rng[16], full[512];
    uint16_t st, st2;
    nvme_cmd_t c;
    nvme_cpl_t r;
    smart_t s0, s1;

    fresh(BAD2, 2);
    cap = g_cap;
    smart_get(&s0);
    out("cmd_admin_bad_opc", "%03x", adm_cmd(0x7F, 0, 0, 0, buf, NULL));
    out("cmd_io_bad_opc", "%03x", io_cmd(0x05, 1, 0, 0, 0, 0, 0, buf, NULL));
    out("cmd_write_zeroes", "%03x", io_cmd(0x08, 1, 0, 0, 0, 0, 0, buf, NULL));
    out("cmd_fw_download", "%03x", adm_cmd(0x11, 0, 0, 0, buf, NULL));
    out("cmd_read_oor", "%03x", io_cmd(0x02, 1, cap, 0, 0, 0, 0, buf, NULL));
    out("cmd_read_cross_end", "%03x", io_cmd(0x02, 1, cap - 1, 1, 0, 0, 0, buf, NULL));
    out("cmd_read_last", "%03x", io_cmd(0x02, 1, cap - 1, 0, 0, 0, 0, buf, NULL));
    out("cmd_write_oor", "%03x", io_cmd(0x01, 1, (uint64_t)cap + 100, 0, 0, 0, 0, buf, NULL));
    out("cmd_io_nsid2", "%03x", io_cmd(0x02, 2, 0, 0, 0, 0, 0, buf, NULL));
    out("cmd_io_nsid0", "%03x", io_cmd(0x02, 0, 0, 0, 0, 0, 0, buf, NULL));
    out("cmd_read_over_mdts", "%03x", io_cmd(0x02, 1, 0, 256, 0, 0, 0, buf, NULL));
    st = m_write(0, 256, 0);
    st2 = io_cmd(0x02, 1, 0, 255, 0, 0, 0, buf, NULL);
    for (i = 0, cdw0 = 0; i < 256; i++)
        if (block_ver(buf + (size_t)i * BLK, i) != (int64_t)m_cur(i))
            cdw0++;
    out("cmd_mdts_rw", "%03x/%03x/%u", st, st2, cdw0);
    out("cmd_flush_bcast", "%03x", io_cmd(0x00, 0xFFFFFFFFu, 0, 0, 0, 0, 0, NULL, NULL));
    out("cmd_flush_nsid2", "%03x", io_cmd(0x00, 2, 0, 0, 0, 0, 0, NULL, NULL));
    memset(rng, 0, sizeof(rng));
    i = 2; memcpy(rng + 4, &i, 4);
    { uint64_t sl = cap - 1; memcpy(rng + 8, &sl, 8); }
    out("cmd_dsm_oor", "%03x", io_cmd(0x09, 1, 0, 0, 0, 4, 0, rng, NULL));
    memset(rng, 0, sizeof(rng));
    i = 10; memcpy(rng + 4, &i, 4);
    st = io_cmd(0x09, 1, 0, 0, 0, 1, 0, rng, NULL);           /* IDR only, no AD */
    out("cmd_dsm_no_ad", "%03x/%u", st, m_verify_exact(0, 10));
    out("cmd_log_bad_lid", "%03x", adm_cmd(0x02, 0xFFFFFFFFu, 0x05 | (127u << 16), 0, buf, NULL));
    out("cmd_log_any_nsid", "%03x", adm_cmd(0x02, 5, 0x02 | (127u << 16), 0, buf, NULL));
    adm_cmd(0x02, 0xFFFFFFFFu, 0x02 | (127u << 16), 0, full, NULL);
    memset(buf, 0xEE, 64);
    st = adm_cmd(0x02, 0xFFFFFFFFu, 0x02 | (3u << 16), 0, buf, NULL);
    out("cmd_log_short", "%03x/%d/%d", st, memcmp(buf, full, 16) == 0, buf[16] == 0xEE && buf[63] == 0xEE);
    out("cmd_id_bad_cns", "%03x", adm_cmd(0x06, 0, 0x10, 0, buf, NULL));
    out("cmd_id_ns_bad_nsid", "%03x", adm_cmd(0x06, 5, 0x00, 0, buf, NULL));
    memset(buf, 0xEE, 16);
    st = adm_cmd(0x06, 0, 0x02, 0, buf, NULL);
    out("cmd_id_nslist", "%03x/%u,%u", st, buf[0] | (buf[1] << 8), buf[4] | (buf[5] << 8));
    out("cmd_setf_bad_fid", "%03x", adm_cmd(0x09, 0, 0x07, 0x00010001, NULL, NULL));
    out("cmd_setf_sv", "%03x", adm_cmd(0x09, 0, 0x06 | (1u << 31), 1, NULL, NULL));
    out("cmd_getf_sel3", "%03x", adm_cmd(0x0A, 0, 0x06 | (3u << 8), 0, NULL, NULL));
    out("cmd_getf_bad_fid", "%03x", adm_cmd(0x0A, 0, 0x0B, 0, NULL, NULL));
    out("cmd_fmt_bad_lbaf", "%03x", adm_cmd(0x80, 1, 0x1, 0, NULL, NULL));
    out("cmd_fmt_ses2", "%03x", adm_cmd(0x80, 1, 2u << 9, 0, NULL, NULL));
    out("cmd_fmt_bad_nsid", "%03x", adm_cmd(0x80, 3, 0, 0, NULL, NULL));
    memset(&c, 0, sizeof(c));
    c.sqid = 1; c.cid = 0x1234; c.opcode = 0x02; c.nsid = 1; c.slba = 5; c.nlb = 0;
    c.cdw10 = 5;
    fw_submit(&c, buf, &r);
    out("cmd_cid_echo", "%04x/%u/%03x", r.cid, r.sqid, r.status);
    smart_get(&s1);
    out("cmd_errlog_delta", "%llu", (unsigned long long)(s1.errlog - s0.errlog));
    out("cmd_rw_cmds", "%llu/%llu", (unsigned long long)(s1.rcmd - s0.rcmd),
        (unsigned long long)(s1.wcmd - s0.wcmd));
    out("viol_cmd", "%u", hsim_violations());
}

static void sc_ident(void)
{
    uint8_t d[4096];
    char t[64];
    int i;

    fresh(BAD2, 2);
    out("id_status", "%03x", adm_cmd(0x06, 0, 0x01, 0, d, NULL));
    out("id_vid_ssvid", "%04x/%04x", d[0] | (d[1] << 8), d[2] | (d[3] << 8));
    memcpy(t, d + 4, 20); t[20] = 0;
    for (i = 0; i < 20; i++) if (t[i] == ' ') t[i] = '_';
    out("id_sn", "%s", t);
    memcpy(t, d + 24, 40); t[40] = 0;
    for (i = 0; i < 40; i++) if (t[i] == ' ') t[i] = '_';
    out("id_mn", "%s", t);
    memcpy(t, d + 64, 8); t[8] = 0;
    for (i = 0; i < 8; i++) if (t[i] == ' ') t[i] = '_';
    out("id_fr", "%s", t);
    out("id_oui_mdts", "%02x%02x%02x/%u", d[73], d[74], d[75], d[77]);
    out("id_ver", "%08x", d[80] | (d[81] << 8) | (d[82] << 16) | ((uint32_t)d[83] << 24));
    out("id_oacs_npss", "%04x/%u", d[256] | (d[257] << 8), d[263]);
    out("id_wctemp_cctemp", "%u/%u", d[266] | (d[267] << 8), d[268] | (d[269] << 8));
    out("id_nn_oncs_vwc", "%u/%04x/%u", d[516] | (d[517] << 8), d[520] | (d[521] << 8), d[525]);
    out("id_sqes_cqes", "%02x/%02x", d[512], d[513]);
    out("ns_status", "%03x", adm_cmd(0x06, 1, 0x00, 0, d, NULL));
    out("ns_nsze_ncap", "%u/%u", d[0] | (d[1] << 8) | (d[2] << 16), d[8] | (d[9] << 8) | (d[10] << 16));
    out("ns_nlbaf_flbas_dlfeat", "%u/%u/%02x", d[25], d[26], d[32]);
    out("ns_lbaf0", "%08x", d[128] | (d[129] << 8) | (d[130] << 16) | ((uint32_t)d[131] << 24));
    m_write(100, 10, 0);
    adm_cmd(0x06, 1, 0x00, 0, d, NULL);
    out("ns_nuse_cached", "%u", d[16] | (d[17] << 8));
    m_flush();
    adm_cmd(0x06, 1, 0x00, 0, d, NULL);
    out("ns_nuse_flushed", "%u", d[16] | (d[17] << 8));
    m_trim(103, 3);
    adm_cmd(0x06, 1, 0x00, 0, d, NULL);
    out("ns_nuse_trim", "%u", d[16] | (d[17] << 8));
}

/* random mixed workload over [0, range) */
static uint32_t mixed(uint32_t seed, uint32_t ops, uint32_t range, int fua_pct)
{
    uint32_t i, op, lba, n, bad = 0, j;
    int64_t v;
    rnd_seed(seed);
    for (i = 0; i < ops; i++) {
        op = rnd() % 100;
        n = 1 + rnd() % 16;
        lba = rnd() % (range - n);
        if (op < 50) {
            m_write(lba, n, (int)(rnd() % 100) < fua_pct);
        } else if (op < 75) {
            for (j = 0; j < n; j++) {
                v = m_read_ver(lba + j, NULL);
                if (v != (int64_t)m_cur(lba + j))
                    bad++;
            }
        } else if (op < 85) {
            m_trim(lba, n);
        } else if (op < 92) {
            m_flush();
        } else {
            m_write(lba, 1 + n % 4, 1);
        }
    }
    return bad + m_verify_exact(0, range);
}

static void sc_integ(void)
{
    uint32_t bad;
    uint16_t st;
    int rc;

    fresh(BAD2, 2);
    out("integ_cache_on", "%u", mixed(101, 6000, 4096, 0));
    fresh(BAD2, 2);
    st = adm_cmd(0x09, 0, 0x06, 0, NULL, NULL);
    m_set_wt(1);
    out("integ_cache_off", "%03x/%u", st, mixed(202, 3000, 4096, 0));
    fresh(BAD2, 2);
    out("integ_fua_mix", "%u", mixed(303, 4000, 4096, 50));
    fresh(BAD2, 2);
    bad = m_verify_exact(0, g_cap);
    out("integ_unwritten_zero", "%u", bad);
    m_write(0, g_cap, 0);
    m_flush();
    out("integ_fill", "%u", m_verify_exact(0, g_cap));
    m_write(1001, 256, 0);
    m_write(5003, 77, 0);
    out("integ_unaligned", "%u", m_verify_exact(990, 1300) + m_verify_exact(5000, 5100));
    m_write(7, 1, 0);
    m_write(7, 1, 0);
    out("integ_cache_overwrite", "%lld", (long long)(m_read_ver(7, NULL) - (int64_t)m_cur(7)));
    m_write(0, g_cap, 0);
    out("integ_refill_gc", "%u", m_verify_exact(0, g_cap));
    fw_shutdown(1);
    rc = boot();
    out("integ_reboot_clean", "%d/%u", rc, m_verify_exact(0, g_cap));
    m_write(2000, 50, 0);
    fw_shutdown(0);
    rc = boot();
    out("integ_reboot_abrupt", "%d/%u", rc, m_verify_exact(0, g_cap));
    st = adm_cmd(0x80, 1, 0, 0, NULL, NULL);
    m_format();
    out("integ_format_ses0", "%03x/%u", st, m_verify_exact(0, g_cap));
    m_write(300, 300, 0);
    st = adm_cmd(0x80, 1, 1u << 9, 0, NULL, NULL);
    m_format();
    out("integ_format_ses1", "%03x/%u", st, m_verify_exact(0, g_cap));
    fw_shutdown(1);
    rc = boot();
    out("integ_format_reboot", "%d/%u", rc, m_verify_exact(0, g_cap));
    out("viol_integ", "%u", hsim_violations());
}

static void sc_smart(void)
{
    smart_t s;
    uint32_t i;

    fresh(BAD2, 2);
    smart_get(&s);
    out("smart_initial", "%03x/%llu/%llu/%u/%u/%u/%02x", s.st, (unsigned long long)s.pc,
        (unsigned long long)s.unsafe, s.spare, s.thr, s.used, s.cw);
    out("smart_temp_initial", "%u", s.temp);
    m_write(0, 251, 0);
    m_write(1000, 1, 1);
    io_cmd(0x01, 1, (uint64_t)g_cap + 5, 0, 0, 0, 0, buf, NULL);
    io_cmd(0x02, 1, 0, 99, 0, 0, 0, buf, NULL);
    io_cmd(0x02, 1, 200, 24, 0, 0, 0, buf, NULL);
    io_cmd(0x02, 1, 5000, 0, 0, 0, 0, buf, NULL);
    smart_get(&s);
    out("smart_du_floor", "%llu/%llu", (unsigned long long)s.duw, (unsigned long long)s.dur);
    out("smart_cmds", "%llu/%llu/%llu", (unsigned long long)s.wcmd, (unsigned long long)s.rcmd,
        (unsigned long long)s.errlog);
    m_write(2000, 124, 0);
    for (i = 0; i < 3; i++)
        io_cmd(0x02, 1, 3000, 0, 0, 0, 0, buf, NULL);
    smart_get(&s);
    out("smart_du_boundary", "%llu/%llu", (unsigned long long)s.duw, (unsigned long long)s.dur);
    for (i = 0; i < 7; i++)
        tick(1800000);
    smart_get(&s);
    out("smart_poh", "%llu", (unsigned long long)s.poh);
    hsim_set_temp(60);
    smart_get(&s);
    out("smart_temp_stale", "%u", s.temp);
    tick(1000);
    smart_get(&s);
    out("smart_temp_after_tick", "%u/%02x", s.temp, s.cw);
    adm_cmd(0x09, 0, 0x04, 330, NULL, NULL);
    smart_get(&s);
    out("smart_cw_tmpth_330", "%02x", s.cw);
    adm_cmd(0x09, 0, 0x04, 333, NULL, NULL);
    smart_get(&s);
    out("smart_cw_tmpth_eq", "%02x", s.cw);
    adm_cmd(0x09, 0, 0x04, 334, NULL, NULL);
    smart_get(&s);
    out("smart_cw_tmpth_334", "%02x", s.cw);
    fw_shutdown(1);
    boot();
    fw_shutdown(1);
    boot();
    smart_get(&s);
    out("smart_after_2_clean", "%llu/%llu/%llu/%llu/%llu", (unsigned long long)s.pc,
        (unsigned long long)s.unsafe, (unsigned long long)s.duw, (unsigned long long)s.wcmd,
        (unsigned long long)s.poh);
    fw_shutdown(0);
    boot();
    smart_get(&s);
    out("smart_after_abrupt", "%llu/%llu", (unsigned long long)s.pc, (unsigned long long)s.unsafe);
    if (setjmp(g_cut_jmp) == 0)
        cut_handler();
    boot();
    smart_get(&s);
    out("smart_after_cut", "%llu/%llu", (unsigned long long)s.pc, (unsigned long long)s.unsafe);
    out("smart_temp_reboot", "%u/%02x", s.temp, s.cw);
}

static void sc_vendor(void)
{
    c0_t c;
    char h[256];
    uint32_t st, prev;

    fresh(BAD2, 2);
    m_write(0, 2000, 0);
    m_flush();
    c0_get(&c);
    hex(h, c.raw, 8);
    out("c0_sig_raw", "%03x/%s", c.st, h);
    out("c0_cdw0", "%u", c.cdw0);
    hex(h, c.raw + 0x10, 4);
    out("c0_bad_raw", "%s", h);
    hex(h, c.raw, 0x2C);
    out("c0_raw_prefix", "%s", h);
    out("c0_free_ec", "%u/%u/%u/%u", c.f[C0_FREE], c.f[C0_MINEC], c.f[C0_MAXEC], c.f[C0_AVGEC]);
    out("c0_nandprog", "%u", c.f[C0_NANDPROG]);
    m_write(5000, 10, 0);
    c0_get(&c);
    out("c0_dirty", "%u", c.f[C0_DIRTY]);
    adm_cmd(0x80, 1, 0, 0, NULL, NULL);
    c0_get(&c);
    out("c0_format_dirty", "%u/%u", c.f[C0_FORMAT], c.f[C0_DIRTY]);
    st = adm_cmd(0xC1, 0, 3, 0, NULL, &prev);
    out("c1_set_debug", "%03x/%u", st, st ? 0 : prev);
    out("c1_bad_level", "%03x", adm_cmd(0xC1, 0, 9, 0, NULL, NULL));
}

static void sc_features(void)
{
    uint32_t v = 0;
    uint16_t st;

    fresh(BAD2, 2);
    st = adm_cmd(0x0A, 0, 0x06, 0, NULL, &v);
    out("feat_vwc_default", "%03x/%u", st, v);
    st = adm_cmd(0x09, 0, 0x06, 0, NULL, NULL);
    adm_cmd(0x0A, 0, 0x06, 0, NULL, &v);
    out("feat_vwc_off", "%03x/%u", st, v);
    adm_cmd(0x0A, 0, 0x06 | (1u << 8), 0, NULL, &v);
    out("feat_vwc_sel_default", "%u", v);
    m_set_wt(1);
    m_write(50, 1, 0);
    if (setjmp(g_cut_jmp) == 0)
        cut_handler();
    boot();
    out("feat_vwc_off_durable", "%lld", (long long)m_read_ver(50, NULL));
    adm_cmd(0x0A, 0, 0x06, 0, NULL, &v);
    out("feat_vwc_reset", "%u", v);
    adm_cmd(0x0A, 0, 0x04, 0, NULL, &v);
    out("feat_tmpth_default", "%u", v);
    st = adm_cmd(0x09, 0, 0x04, 0x150, NULL, NULL);
    adm_cmd(0x0A, 0, 0x04, 0, NULL, &v);
    out("feat_tmpth_set", "%03x/%u", st, v);
    out("feat_tmpth_badsel", "%03x", adm_cmd(0x09, 0, 0x04, 0x150 | (1u << 16), NULL, NULL));
    out("feat_tmpth_under", "%03x", adm_cmd(0x09, 0, 0x04, 0x100 | (1u << 20), NULL, NULL));
    st = adm_cmd(0x09, 0, 0x02, 2, NULL, NULL);
    adm_cmd(0x0A, 0, 0x02, 0, NULL, &v);
    out("feat_ps_set", "%03x/%u", st, v);
    out("feat_ps_bad", "%03x", adm_cmd(0x09, 0, 0x02, 3, NULL, NULL));
    fw_shutdown(1);
    boot();
    {
        uint32_t a = 0, b = 0, d = 0;
        adm_cmd(0x0A, 0, 0x06, 0, NULL, &a);
        adm_cmd(0x0A, 0, 0x04, 0, NULL, &b);
        adm_cmd(0x0A, 0, 0x02, 0, NULL, &d);
        out("feat_reset_reboot", "%u/%u/%u", a, b, d);
    }
}

/* part 2 (t_ssd2.c) */
void sc_gc_random(void);
void sc_wl(void);
void sc_bb_factory(void);
void sc_bb_progfail(void);
void sc_bb_erasefail(void);
void sc_bb_spare(void);
void sc_rr(void);
void sc_rd(void);
void sc_pl(void);
void sc_pl_misc(void);
void sc_thermal(void);
void sc_compat_w(void);
void sc_compat_r(void);

static const struct { const char *name; void (*fn)(void); } SC[] = {
    { "cmd", sc_cmd }, { "ident", sc_ident }, { "integ", sc_integ }, { "smart", sc_smart },
    { "vendor", sc_vendor }, { "features", sc_features }, { "gc_random", sc_gc_random },
    { "wl", sc_wl }, { "bb_factory", sc_bb_factory }, { "bb_progfail", sc_bb_progfail },
    { "bb_erasefail", sc_bb_erasefail }, { "bb_spare", sc_bb_spare }, { "rr", sc_rr },
    { "rd", sc_rd }, { "pl", sc_pl }, { "pl_misc", sc_pl_misc }, { "thermal", sc_thermal },
    { "compat_w", sc_compat_w }, { "compat_r", sc_compat_r },
};

int main(int argc, char **argv)
{
    int i;
    if (argc < 2)
        return 2;
    for (i = 2; i + 1 < argc; i += 2) {
        if (!strcmp(argv[i], "--in")) a_in = argv[i + 1];
        else if (!strcmp(argv[i], "--out")) a_out = argv[i + 1];
        else if (!strcmp(argv[i], "--state")) a_state = argv[i + 1];
        else if (!strcmp(argv[i], "--tag")) a_tag = argv[i + 1];
        else if (!strcmp(argv[i], "--mode")) a_mode = argv[i + 1];
        else if (!strcmp(argv[i], "--n")) a_n = (uint32_t)strtoul(argv[i + 1], NULL, 0);
    }
    for (i = 0; i < (int)(sizeof(SC) / sizeof(SC[0])); i++)
        if (!strcmp(argv[1], SC[i].name)) {
            SC[i].fn();
            out("done", "%s", argv[1]);
            return 0;
        }
    fprintf(stderr, "unknown scenario %s\n", argv[1]);
    return 2;
}
