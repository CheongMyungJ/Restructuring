/* t_ssd2.c - hidden harness scenarios (part 2) */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "t_common.h"

extern const char *a_in, *a_out, *a_state, *a_tag, *a_mode;
extern uint32_t a_n;

static const uint32_t BAD2[2] = { 37, 61 };
static uint8_t buf[MDTS * BLK];

static void fresh(const uint32_t *bad, int nbad)
{
    hsim_reset(bad, nbad);
    m_reset();
    out("init", "%d", boot());
}

static void cut_now(void)
{
    if (setjmp(g_cut_jmp) == 0)
        cut_handler();
}

void sc_gc_random(void)
{
    c0_t a, b, c;
    uint32_t i;

    fresh(BAD2, 2);
    m_write(0, g_cap, 0);
    rnd_seed(303);
    for (i = 0; i < 2 * g_cap; i++)
        m_write(rnd() % g_cap, 1, 0);
    m_flush();
    c0_get(&a);
    out("gc_count", "%u", a.f[C0_GC]);
    out("gc_avg_ec", "%u", a.f[C0_AVGEC]);
    out("gc_ec_spread", "%u", a.f[C0_MAXEC] - a.f[C0_MINEC]);
    out("gc_wl_random", "%u", a.f[C0_WL]);
    out("gc_nandprog", "%u", a.f[C0_NANDPROG]);
    out("integ_gc_random", "%u", m_verify_exact(0, g_cap));
    c0_get(&a);
    for (i = 0; i < 12; i++)
        tick(2500);
    c0_get(&b);
    out("gc_idle", "%u/%u", b.f[C0_GC] - a.f[C0_GC], b.f[C0_FREE]);
    for (i = 0; i < g_cap / 2; i++)
        m_write(rnd() % g_cap, 1, 0);
    m_flush();
    c0_get(&a);
    hsim_set_temp(75);
    tick(1000);
    for (i = 0; i < 5; i++)
        tick(2500);
    c0_get(&b);
    hsim_set_temp(40);
    tick(1000);
    for (i = 0; i < 3; i++)
        tick(2500);
    c0_get(&c);
    out("gc_idle_thermal", "%u/%u/%d", b.f[C0_THERM], b.f[C0_GC] - a.f[C0_GC], c.f[C0_GC] > b.f[C0_GC]);
    out("integ_gc_after_idle", "%u", m_verify_exact(0, g_cap));
    out("viol_gc", "%u", hsim_violations());
}

void sc_wl(void)
{
    c0_t a;
    uint32_t i, cold;

    fresh(NULL, 0);
    cold = g_cap * 70 / 100;
    m_write(0, cold, 0);
    m_flush();
    rnd_seed(505);
    for (i = 0; i < 150000; i++)
        m_write(cold + rnd() % (g_cap / 4), 1, 0);
    m_flush();
    c0_get(&a);
    out("wl_count", "%u", a.f[C0_WL]);
    out("wl_gc_count", "%u", a.f[C0_GC]);
    out("wl_ec_spread", "%u", a.f[C0_MAXEC] - a.f[C0_MINEC]);
    out("wl_avg_ec", "%u", a.f[C0_AVGEC]);
    out("integ_wl", "%u", m_verify_exact(0, g_cap));
    out("viol_wl", "%u", hsim_violations());
}

void sc_bb_factory(void)
{
    static const uint32_t bad5[5] = { 12, 25, 40, 77, 90 };
    c0_t c;
    smart_t s;

    fresh(bad5, 5);
    c0_get(&c);
    smart_get(&s);
    out("bb_factory_counts", "%u/%u/%u", c.f[C0_BAD], c.f[C0_GROWN], s.spare);
    m_write(0, g_cap, 0);
    m_flush();
    out("bb_factory_fill", "%u", m_verify_exact(0, g_cap));
    out("viol_bb_factory", "%u", hsim_violations());
}

void sc_bb_progfail(void)
{
    c0_t c;
    smart_t s0, s;

    fresh(BAD2, 2);
    smart_get(&s0);
    m_write(0, 300, 0);
    m_flush();
    m_write_inj(1000, INJ_PF, 0, 7001);
    m_write(1001, 20, 0);
    m_flush();
    c0_get(&c);
    smart_get(&s);
    out("bb_pf_counts", "%u/%u/%u", c.f[C0_PFAIL], c.f[C0_GROWN], c.f[C0_BAD]);
    out("bb_pf_spare", "%u/%u/%02x", s0.spare, s.spare, s.cw);
    out("bb_pf_data", "%u", m_verify_exact(0, 1100));
    m_write(0, 4000, 0);
    m_flush();
    fw_shutdown(1);
    boot();
    c0_get(&c);
    smart_get(&s);
    out("bb_pf_persist", "%u/%u/%u", c.f[C0_GROWN], c.f[C0_BAD], s.spare);
    out("bb_pf_data_reboot", "%u", m_verify_exact(0, 4100));
    out("viol_bb_pf", "%u", hsim_violations());
}

void sc_bb_erasefail(void)
{
    c0_t c;
    smart_t s;

    fresh(BAD2, 2);
    m_write(0, 1000, 0);
    m_flush();
    hsim_fail_next_erase();
    m_write(1000, 2000, 0);
    m_flush();
    c0_get(&c);
    smart_get(&s);
    out("bb_ef_counts", "%u/%u/%u", c.f[C0_EFAIL], c.f[C0_GROWN], c.f[C0_BAD]);
    out("bb_ef_spare", "%u", s.spare);
    out("bb_ef_data", "%u", m_verify_exact(0, 3000));
}

void sc_bb_spare(void)
{
    static const uint32_t b10[10] = { 15, 20, 25, 30, 35, 40, 45, 50, 55, 60 };
    smart_t s;

    fresh(b10, 9);
    smart_get(&s);
    out("bb_spare9", "%u/%02x", s.spare, s.cw);
    fresh(b10, 10);
    smart_get(&s);
    out("bb_spare10", "%u/%02x", s.spare, s.cw);
    m_write(0, 1000, 0);
    m_flush();
    out("bb_spare10_io", "%u", m_verify_exact(0, 1000));
}

void sc_rr(void)
{
    static const uint32_t L[5] = { 2, 3, 4, 6, 9 };
    c0_t a, b, c, d;
    smart_t s0, s1;
    uint16_t st, st2;
    int64_t v, v2;
    uint32_t i, lba;
    char key[32];

    fresh(BAD2, 2);
    for (i = 0; i < 5; i++) {
        lba = 100 + i;
        m_flush();
        m_write_inj(lba, INJ_RR, L[i], 5000 + i);
        m_flush();
        smart_get(&s0);
        c0_get(&a);
        v = m_read_ver(lba, &st);
        c0_get(&b);
        tick(1000);
        c0_get(&c);
        v2 = m_read_ver(lba, &st2);
        c0_get(&d);
        smart_get(&s1);
        sprintf(key, "rr_l%u", L[i]);
        out(key, "%03x/%d/%u/%u/%u/%03x/%d/%u", st, v == (int64_t)m_cur(lba), b.f[C0_RR] - a.f[C0_RR],
            c.f[C0_REF] - b.f[C0_REF], c.f[C0_RRREF] - b.f[C0_RRREF], st2,
            v2 == (int64_t)m_cur(lba), d.f[C0_RR] - c.f[C0_RR]);
        sprintf(key, "rr_l%u_smart", L[i]);
        out(key, "%llu/%llu", (unsigned long long)(s1.media - s0.media),
            (unsigned long long)(s1.errlog - s0.errlog));
    }
    m_write(104, 1, 0);
    m_flush();
    v = m_read_ver(104, &st);
    out("rr_unc_rewrite", "%03x/%d", st, v == (int64_t)m_cur(104));
    c0_get(&a);
    out("rr_totals", "%u/%u/%u", a.f[C0_RR], a.f[C0_REF], a.f[C0_RRREF]);
    out("rr_data_all", "%u", m_verify_exact(0, 200));
}

void sc_rd(void)
{
    c0_t c;
    uint32_t i;
    int64_t v;

    fresh(BAD2, 2);
    m_write(500, 1, 0);
    m_flush();
    for (i = 0; i < 20000; i++)
        io_cmd(0x02, 1, 500, 0, 0, 0, 0, buf, NULL);
    tick(1000);
    c0_get(&c);
    out("rd_at_limit", "%u/%u", c.f[C0_REF], c.f[C0_RDREF]);
    io_cmd(0x02, 1, 500, 0, 0, 0, 0, buf, NULL);
    tick(1000);
    c0_get(&c);
    out("rd_over_limit", "%u/%u/%u", c.f[C0_REF], c.f[C0_RDREF], c.f[C0_RRREF]);
    v = m_read_ver(500, NULL);
    out("rd_data", "%d", v == (int64_t)m_cur(500));
    for (i = 0; i < 20001; i++)
        io_cmd(0x02, 1, 500, 0, 0, 0, 0, buf, NULL);
    tick(1000);
    c0_get(&c);
    out("rd_second", "%u/%u", c.f[C0_REF], c.f[C0_RDREF]);
}

/* power-loss workload: writes / FUA / trims / flushes over the whole range */
static void pl_workload(uint32_t ops)
{
    uint32_t i, op, n, lba;
    for (i = 0; i < ops; i++) {
        op = rnd() % 100;
        n = 1 + rnd() % 32;
        lba = rnd() % (g_cap - 40);
        if (op < 62)
            m_write(lba, n, 0);
        else if (op < 72)
            m_write(lba, 1 + n % 4, 1);
        else if (op < 80)
            m_trim(lba, 1 + n % 8);
        else if (op < 90)
            io_cmd(0x02, 1, lba, n - 1, 0, 0, 0, buf, NULL) == 0 ? (void)0 : (void)0;
        else
            m_flush();
    }
}

static void pl_prepare(void)
{
    fresh(BAD2, 2);
    m_write(0, g_cap * 85 / 100, 0);
    m_flush();
    fw_shutdown(1);
    boot();
}

void sc_pl(void)
{
    smart_t s0, s1;
    uint32_t bad = 0, post = 0;
    int rc, rc2 = -99;
    char key[48];

    pl_prepare();
    smart_get(&s0);
    rnd_seed(404 + a_n);
    if (setjmp(g_cut_jmp) == 0) {
        hsim_arm_cut(a_n, cut_handler);
        pl_workload(3000);
        cut_handler();
    }
    hsim_disarm_cut();
    rc = boot();
    if (rc == 0) {
        bad = m_verify_durable(0, g_cap);
        smart_get(&s1);
        m_write(100, 64, 0);
        m_flush();
        post = m_verify_exact(0, g_cap);
        fw_shutdown(1);
        rc2 = boot();
        post += m_verify_exact(0, g_cap);
    } else {
        memset(&s1, 0, sizeof(s1));
    }
    sprintf(key, "pl_cut_%s", a_tag);
    out(key, "%d/%u/%lld/%lld/%d/%u", rc, bad, (long long)(s1.unsafe - s0.unsafe),
        (long long)(s1.pc - s0.pc), rc2, post);
    sprintf(key, "viol_pl_%s", a_tag);
    out(key, "%u", hsim_violations());
}

static const char *oldnew(int64_t v, uint32_t vold, uint32_t vnew)
{
    return v == (int64_t)vnew ? "new" : (v == (int64_t)vold ? "old" : "bad");
}

void sc_pl_misc(void)
{
    uint32_t v1, v2;
    smart_t s0, s1;
    int rc;

    fresh(BAD2, 2);
    m_write(7, 1, 0); m_flush(); v1 = m_cur(7);
    m_write(7, 1, 0); v2 = m_cur(7);
    cut_now(); boot();
    out("pl_cached_lost", "%s", oldnew(m_read_ver(7, NULL), v1, v2));
    v1 = m_cur(8); m_write(8, 1, 0); v2 = m_cur(8); m_flush();
    cut_now(); boot();
    out("pl_flush_survives", "%s", oldnew(m_read_ver(8, NULL), v1, v2));
    v1 = m_cur(9); m_write(9, 1, 1); v2 = m_cur(9);
    cut_now(); boot();
    out("pl_fua_survives", "%s", oldnew(m_read_ver(9, NULL), v1, v2));
    smart_get(&s0);
    v1 = m_cur(10); m_write(10, 1, 0); v2 = m_cur(10);
    fw_shutdown(0); boot();
    smart_get(&s1);
    out("pl_abrupt_shutdown", "%s/%llu", oldnew(m_read_ver(10, NULL), v1, v2),
        (unsigned long long)(s1.unsafe - s0.unsafe));
    smart_get(&s0);
    v1 = m_cur(11); m_write(11, 1, 0); v2 = m_cur(11);
    fw_shutdown(1); boot();
    smart_get(&s1);
    out("pl_clean_shutdown", "%s/%llu", oldnew(m_read_ver(11, NULL), v1, v2),
        (unsigned long long)(s1.unsafe - s0.unsafe));

    /* cut during the workload, then again during the recovery boot */
    pl_prepare();
    rnd_seed(4242);
    if (setjmp(g_cut_jmp) == 0) {
        hsim_arm_cut(300, cut_handler);
        pl_workload(3000);
        cut_handler();
    }
    if (setjmp(g_cut_jmp) == 0) {
        hsim_arm_cut(0, cut_handler);
        boot();
    }
    hsim_disarm_cut();
    rc = boot();
    out("pl_double_cut", "%d/%u", rc, rc == 0 ? m_verify_durable(0, g_cap) : 999999);

    /* cut during FORMAT NVM (user data erase) */
    pl_prepare();
    m_format();
    if (setjmp(g_cut_jmp) == 0) {
        hsim_arm_cut(20, cut_handler);
        adm_cmd(0x80, 1, 1u << 9, 0, NULL, NULL);
        cut_handler();
    }
    hsim_disarm_cut();
    rc = boot();
    out("pl_format_cut", "%d/%u", rc, rc == 0 ? m_verify_durable(0, g_cap) : 999999);
    out("viol_pl_misc", "%u", hsim_violations());
}

void sc_thermal(void)
{
    c0_t c;
    smart_t s;
    uint32_t i, d2, d0, v1, v2, ev;

    fresh(BAD2, 2);
    hsim_set_temp(75);
    c0_get(&c);
    out("th_no_sample", "%u", c.f[C0_THERM]);
    tick(500);
    c0_get(&c);
    out("th_half_interval", "%u", c.f[C0_THERM]);
    tick(500);
    c0_get(&c);
    out("th_l1", "%u/%u", c.f[C0_THERM], c.f[C0_THROT]);
    hsim_set_temp(82); tick(1000); c0_get(&c);
    out("th_l2", "%u/%u", c.f[C0_THERM], c.f[C0_THROT]);
    hsim_set_temp(90); tick(1000); c0_get(&c); smart_get(&s);
    out("th_l3", "%u/%u/%u/%02x", c.f[C0_THERM], c.f[C0_THROT], s.temp, s.cw);
    hsim_set_temp(84); tick(1000); c0_get(&c);
    out("th_hold", "%u/%u", c.f[C0_THERM], c.f[C0_THROT]);
    hsim_set_temp(81); tick(1000); c0_get(&c);
    out("th_drop1", "%u", c.f[C0_THERM]);
    hsim_set_temp(77); tick(1000); c0_get(&c);
    out("th_hyst_edge", "%u", c.f[C0_THERM]);
    hsim_set_temp(60); tick(1000); c0_get(&c);
    out("th_drop_all", "%u/%u", c.f[C0_THERM], c.f[C0_THROT]);

    hsim_set_temp(82); tick(1000);
    m_flush();
    for (i = 0; i < 40; i++)
        m_write(6000 + i * 3, 1, 0);
    c0_get(&c); d2 = c.f[C0_DIRTY];
    hsim_set_temp(40); tick(1000);
    m_flush();
    for (i = 0; i < 40; i++)
        m_write(7000 + i * 3, 1, 0);
    c0_get(&c); d0 = c.f[C0_DIRTY];
    out("th_cache_limit", "%u/%u", d2, d0);
    m_flush();

    hsim_set_temp(90); tick(1000);
    v1 = m_cur(3000); m_write(3000, 1, 0); v2 = m_cur(3000);
    cut_now(); boot();
    out("th_l3_writethrough", "%s", oldnew(m_read_ver(3000, NULL), v1, v2));
    c0_get(&c);
    out("th_boot_level", "%u/%u", c.f[C0_THERM], c.f[C0_THROT]);
    hsim_set_temp(40); tick(1000);
    v1 = m_cur(3001); m_write(3001, 1, 0); v2 = m_cur(3001);
    cut_now(); boot();
    out("th_l0_cached", "%s", oldnew(m_read_ver(3001, NULL), v1, v2));
    c0_get(&c); ev = c.f[C0_THROT];
    fw_shutdown(1); boot();
    c0_get(&c);
    out("th_events_persist", "%u/%u", ev, c.f[C0_THROT]);
}

/* ---- on-NAND compatibility (image based, may run with different builds) ---- */
void sc_compat_w(void)
{
    smart_t s;
    uint64_t ex[4];
    uint32_t i, half;

    fresh(BAD2, 2);
    half = g_cap / 2;
    m_write(0, half, 0);
    rnd_seed(606);
    for (i = 0; i < 6000; i++) {
        m_write(rnd() % (half - 8), 1 + rnd() % 8, 0);
        if (i % 500 == 499)
            m_trim(rnd() % (half - 16), 16);
    }
    m_flush();
    if (!strcmp(a_mode, "pf")) {
        m_write_inj(200, INJ_PF, 0, 9001);
        m_write(201, 50, 0);
        m_flush();
    }
    smart_get(&s);
    ex[0] = s.pc; ex[1] = s.unsafe; ex[2] = s.duw; ex[3] = s.wcmd;
    if (!strcmp(a_mode, "cut")) {
        if (setjmp(g_cut_jmp) == 0) {
            hsim_arm_cut(a_n, cut_handler);
            for (i = 0; i < 3000; i++) {
                m_write(rnd() % (half - 8), 1 + rnd() % 8, (i % 7) == 0);
                if (i % 40 == 39)
                    m_flush();
            }
            cut_handler();
        }
        hsim_disarm_cut();
    } else {
        fw_shutdown(1);
    }
    out("cw_save", "%d/%d", hsim_save(a_out), m_save(a_state, ex, 4));
}

void sc_compat_r(void)
{
    uint64_t ex[4];
    smart_t s;
    c0_t c;
    uint8_t d[4096];
    char key[1024], sn[21];
    uint32_t bad, i;
    int rc;

    if (hsim_load(a_in) != 0 || m_load(a_state, ex, 4) != 0) {
        out("cr_load", "fail");
        return;
    }
    if (!strcmp(a_mode, "aged"))
        hsim_age_ckpt(a_n);
    rc = boot();
    sprintf(key, "compat_%s_mount", a_tag);
    out(key, "%d", rc);
    if (rc != 0)
        return;
    smart_get(&s);
    if (!strcmp(a_mode, "aged")) {
        sprintf(key, "compat_%s_smart", a_tag);
        out(key, "%u/%02x/%u", s.used, s.cw, s.spare);
        return;
    }
    bad = m_verify_durable(0, g_cap);
    c0_get(&c);
    adm_cmd(0x06, 0, 1, 0, d, NULL);
    memcpy(sn, d + 4, 20); sn[20] = 0;
    for (i = 0; i < 20; i++) if (sn[i] == ' ') sn[i] = '_';
    sprintf(key, "compat_%s_data", a_tag);
    out(key, "%u", bad);
    sprintf(key, "compat_%s_counters", a_tag);
    out(key, "%lld/%lld", (long long)(s.pc - ex[0]), (long long)(s.unsafe - ex[1]));
    if (!strcmp(a_mode, "clean")) {
        sprintf(key, "compat_%s_smart", a_tag);
        out(key, "%lld/%lld", (long long)(s.duw - ex[2]), (long long)(s.wcmd - ex[3]));
    }
    sprintf(key, "compat_%s_bad", a_tag);
    out(key, "%u/%u/%u", c.f[C0_BAD], c.f[C0_GROWN], s.spare);
    sprintf(key, "compat_%s_sn_cap", a_tag);
    out(key, "%s/%u", sn, g_cap);
    if (a_out) {
        rnd_seed(707);
        for (i = 0; i < 4000; i++)
            m_write(rnd() % (g_cap - 8), 1 + rnd() % 8, 0);
        m_flush();
        smart_get(&s);
        ex[0] = s.pc; ex[1] = s.unsafe; ex[2] = s.duw; ex[3] = s.wcmd;
        fw_shutdown(1);
        snprintf(key, sizeof(key), "%s.state", a_out);
        out("cr_save", "%d/%d", hsim_save(a_out), m_save(key, ex, 4));
    }
}
