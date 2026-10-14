/*
 * ssdcli.c - developer test CLI for the sim build
 *
 *   usage: ssdcli [script]      (stdin if no script)
 *
 *   init [img]                power on (optionally load NAND image first)
 *   bad <blk> [blk..]         factory bad blocks (before first init)
 *   write <slba> <n> [fua]    write test pattern
 *   read <slba> <n>           read + verify against model
 *   rand <count> <seed> [max_lba]   random 4K writes
 *   verify                    verify every written LBA
 *   flush | trim <slba> <n> | format [ses]
 *   smart | c0 | id | ns
 *   getf <fid> | setf <fid> <val> | dbg <level>
 *   tick <ms> [repeat] | temp <c>
 *   weak <blk> <page> <lvl> | failprog | failerase
 *   cut <nops>                power cut after n NAND program/erase
 *   shutdown [abrupt] | save <img> | load <img> | check | quit
 *
 *  2018.10 jhkim
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
#include "fw_api.h"
#include "fw_config.h"
#include "sim.h"

#define NSID_ALL_CLI    0xFFFFFFFFu
#ifndef MIN
#define MIN(a, b)       (((a) < (b)) ? (a) : (b))
#endif

static uint32_t  s_gen[FTL_MAX_LBAS];       /* expected pattern generation (0 = zero) */
static uint8_t   s_buf[MDTS_LBAS * LBA_SIZE];
static jmp_buf   s_cut_jmp;
static uint32_t  s_bad[64];
static int       s_nbad, s_sim_ready;
static uint32_t  s_gen_next = 1;
static uint64_t  s_cap;

static void fill(uint8_t *p, uint32_t lba, uint32_t gen)
{
    uint32_t i, x = lba * 2654435761u ^ gen;

    if (gen == 0) {
        memset(p, 0, LBA_SIZE);
        return;
    }
    for (i = 0; i < LBA_SIZE / 4; i++) {
        x = x * 1103515245u + 12345u;
        memcpy(p + i * 4, &x, 4);
    }
    memcpy(p, &lba, 4);
    memcpy(p + 4, &gen, 4);
}

static uint16_t cmd(uint16_t sqid, uint8_t opc, uint32_t nsid, uint64_t slba, uint32_t nlb,
                    uint32_t c10, uint32_t c11, uint32_t c12, void *buf, uint32_t *cdw0)
{
    nvme_cmd_t c;
    nvme_cpl_t r;

    memset(&c, 0, sizeof(c));
    c.sqid = sqid; c.opcode = opc; c.nsid = nsid; c.slba = slba; c.nlb = nlb;
    c.cdw10 = c10; c.cdw11 = c11; c.cdw12 = c12;
    fw_submit(&c, buf, &r);
    if (cdw0)
        *cdw0 = r.cdw0;
    return r.status;
}

static void on_cut(void)
{
    longjmp(s_cut_jmp, 1);
}

static uint64_t le(const uint8_t *p, int n)
{
    uint64_t v = 0;
    while (n--)
        v = (v << 8) | p[n];
    return v;
}

static void do_init(const char *img)
{
    uint8_t id[4096];
    int rc;

    if (!s_sim_ready) {
        if (img) sim_nand_load(img); else sim_nand_init(s_bad, s_nbad);
        s_sim_ready = 1;
    } else if (img) {
        sim_nand_load(img);
    }
    rc = fw_init();
    printf("init rc=%d\n", rc);
    if (rc == 0 && cmd(0, NVME_ADM_IDENTIFY, 1, 0, 0, 0, 0, 0, id, NULL) == 0)
        s_cap = le(id, 8);
}

static void do_rw(int wr, uint64_t slba, uint32_t n, int fua)
{
    uint32_t i, done, chunk, bad = 0;
    uint16_t st;
    uint8_t exp[LBA_SIZE];

    for (done = 0; done < n; done += chunk) {
        chunk = MIN(n - done, MDTS_LBAS);
        if (wr) {
            for (i = 0; i < chunk; i++) {
                if (slba + done + i < FTL_MAX_LBAS)
                    s_gen[slba + done + i] = s_gen_next;
                fill(s_buf + i * LBA_SIZE, (uint32_t)(slba + done + i), s_gen_next);
            }
            s_gen_next++;
            st = cmd(1, NVME_IO_WRITE, 1, slba + done, chunk - 1, 0, 0, fua ? (1u << 30) : 0, s_buf, NULL);
        } else {
            st = cmd(1, NVME_IO_READ, 1, slba + done, chunk - 1, 0, 0, 0, s_buf, NULL);
            for (i = 0; st == 0 && i < chunk; i++) {
                fill(exp, (uint32_t)(slba + done + i), s_gen[slba + done + i]);
                if (memcmp(exp, s_buf + i * LBA_SIZE, LBA_SIZE) != 0)
                    bad++;
            }
        }
        if (st) {
            printf("%s lba %llu status %03x\n", wr ? "write" : "read",
                   (unsigned long long)(slba + done), st);
            return;
        }
    }
    if (!wr)
        printf("read %u lbas, %u mismatch\n", n, bad);
}

static void do_smart(void)
{
    uint8_t l[512];
    uint16_t st = cmd(0, NVME_ADM_GET_LOG_PAGE, NSID_ALL_CLI, 0, 0, 0x02 | (127u << 16), 0, 0, l, NULL);

    if (st) { printf("smart status %03x\n", st); return; }
    printf("cw=%02x temp=%uK spare=%u%% thr=%u%% used=%u%%\n", l[0], (unsigned)le(l + 1, 2), l[3], l[4], l[5]);
    printf("dur=%llu duw=%llu rcmd=%llu wcmd=%llu pc=%llu poh=%llu unsafe=%llu media=%llu errlog=%llu\n",
           (unsigned long long)le(l + 32, 8), (unsigned long long)le(l + 48, 8),
           (unsigned long long)le(l + 64, 8), (unsigned long long)le(l + 80, 8),
           (unsigned long long)le(l + 112, 8), (unsigned long long)le(l + 128, 8),
           (unsigned long long)le(l + 144, 8), (unsigned long long)le(l + 160, 8),
           (unsigned long long)le(l + 176, 8));
}

static void do_c0(void)
{
    static const char *nm[] = { "sig", "ver", "gc", "wl", "bad", "grown", "rr", "refresh",
        "rr_ref", "rd_ref", "free", "min_ec", "max_ec", "avg_ec", "pfail", "efail",
        "therm", "throttle", "dirty", "ckpt", "nandprog", "format", "dbg" };
    uint8_t b[512];
    uint32_t i, n;
    uint16_t st = cmd(0, NVME_ADM_VS_DUMP_COUNTERS, 0, 0, 0, 0, 0, 0, b, &n);

    if (st) { printf("c0 status %03x\n", st); return; }
    for (i = 0; i < n && i < 23; i++)
        printf("%s=%u%s", nm[i], (b[i*4] << 24) | (b[i*4+1] << 16) | (b[i*4+2] << 8) | b[i*4+3],
               (i % 8 == 7) ? "\n" : " ");
    printf("\n");
}

static void do_verify(void)
{
    uint64_t lba;
    uint32_t bad = 0;
    uint8_t exp[LBA_SIZE];

    for (lba = 0; lba < s_cap && lba < FTL_MAX_LBAS; lba++) {
        if (cmd(1, NVME_IO_READ, 1, lba, 0, 0, 0, 0, s_buf, NULL) != 0) { bad++; continue; }
        fill(exp, (uint32_t)lba, s_gen[lba]);
        if (memcmp(exp, s_buf, LBA_SIZE) != 0)
            bad++;
    }
    printf("verify %llu lbas, %u mismatch\n", (unsigned long long)s_cap, bad);
}

int main(int argc, char **argv)
{
    FILE *in = stdin;
    char line[256], op[32], a1[128];
    unsigned long long v1, v2, v3;
    uint32_t c0;
    int n;

    if (argc > 1 && !(in = fopen(argv[1], "r"))) {
        perror(argv[1]);
        return 1;
    }
    while (fgets(line, sizeof(line), in)) {
        if (line[0] == '#' || line[0] == '\n')
            continue;
        v1 = v2 = v3 = 0; a1[0] = 0;
        n = sscanf(line, "%31s %llu %llu %llu", op, &v1, &v2, &v3);
        if (n < 1)
            continue;
        if (setjmp(s_cut_jmp)) {
            printf("*** POWER CUT ***\n");
            continue;
        }
        if (!strcmp(op, "init")) {
            sscanf(line, "%*s %127s", a1);
            do_init(a1[0] ? a1 : NULL);
        } else if (!strcmp(op, "bad")) {
            char *p = line + 3;
            while (s_nbad < 64 && sscanf(p, "%llu%n", &v1, &n) == 1) { s_bad[s_nbad++] = (uint32_t)v1; p += n; }
        } else if (!strcmp(op, "write")) {
            do_rw(1, v1, (uint32_t)v2, strstr(line, "fua") != NULL);
        } else if (!strcmp(op, "read")) {
            do_rw(0, v1, (uint32_t)v2, 0);
        } else if (!strcmp(op, "rand")) {
            uint64_t i, x = v2 ? v2 : 1, mx = v3 ? v3 : s_cap;
            for (i = 0; i < v1; i++) {
                x ^= x << 13; x ^= x >> 7; x ^= x << 17;
                do_rw(1, x % mx, 1, 0);
            }
        } else if (!strcmp(op, "verify")) {
            do_verify();
        } else if (!strcmp(op, "flush")) {
            printf("flush %03x\n", cmd(1, NVME_IO_FLUSH, 1, 0, 0, 0, 0, 0, NULL, NULL));
        } else if (!strcmp(op, "trim")) {
            uint8_t r[16] = {0};
            uint64_t i;
            memcpy(r + 4, &v2, 4); memcpy(r + 8, &v1, 8);
            printf("trim %03x\n", cmd(1, NVME_IO_DSM, 1, 0, 0, 0, 4, 0, r, NULL));
            for (i = v1; i < v1 + v2 && i < FTL_MAX_LBAS; i++) s_gen[i] = 0;
        } else if (!strcmp(op, "format")) {
            printf("format %03x\n", cmd(0, NVME_ADM_FORMAT_NVM, 1, 0, 0, (uint32_t)v1 << 9, 0, 0, NULL, NULL));
            memset(s_gen, 0, sizeof(s_gen));
        } else if (!strcmp(op, "smart")) {
            do_smart();
        } else if (!strcmp(op, "c0")) {
            do_c0();
        } else if (!strcmp(op, "id") || !strcmp(op, "ns")) {
            uint8_t d[4096];
            uint16_t st = cmd(0, NVME_ADM_IDENTIFY, 1, 0, 0, op[0] == 'i' ? 1 : 0, 0, 0, d, NULL);
            if (op[0] == 'i')
                printf("id %03x vid=%04x sn=%.20s mn=%.40s fr=%.8s\n", st, (unsigned)le(d, 2), d + 4, d + 24, d + 64);
            else
                printf("ns %03x nsze=%llu ncap=%llu nuse=%llu\n", st, (unsigned long long)le(d, 8),
                       (unsigned long long)le(d + 8, 8), (unsigned long long)le(d + 16, 8));
        } else if (!strcmp(op, "getf")) {
            uint16_t st = cmd(0, NVME_ADM_GET_FEATURES, 0, 0, 0, (uint32_t)v1, 0, 0, NULL, &c0);
            printf("getf %03x cdw0=%u\n", st, c0);
        } else if (!strcmp(op, "setf")) {
            printf("setf %03x\n", cmd(0, NVME_ADM_SET_FEATURES, 0, 0, 0, (uint32_t)v1, (uint32_t)v2, 0, NULL, NULL));
        } else if (!strcmp(op, "dbg")) {
            printf("dbg %03x\n", cmd(0, NVME_ADM_VS_SET_DEBUG, 0, 0, 0, (uint32_t)v1, 0, 0, NULL, &c0));
        } else if (!strcmp(op, "tick")) {
            unsigned long long i, rep = v2 ? v2 : 1;
            for (i = 0; i < rep; i++) { sim_advance_ms((uint32_t)v1); fw_tick((uint32_t)v1); }
        } else if (!strcmp(op, "temp")) {
            sim_set_temp((int32_t)v1);
        } else if (!strcmp(op, "weak")) {
            sim_nand_set_weak((uint32_t)v1, (uint32_t)v2, (uint32_t)v3);
        } else if (!strcmp(op, "failprog")) {
            sim_nand_fail_next_program();
        } else if (!strcmp(op, "failerase")) {
            sim_nand_fail_next_erase();
        } else if (!strcmp(op, "cut")) {
            sim_power_cut_after((uint32_t)v1, on_cut);
        } else if (!strcmp(op, "shutdown")) {
            fw_shutdown(strstr(line, "abrupt") == NULL);
        } else if (!strcmp(op, "save")) {
            sscanf(line, "%*s %127s", a1);
            printf("save %d\n", sim_nand_save(a1));
        } else if (!strcmp(op, "load")) {
            sscanf(line, "%*s %127s", a1);
            printf("load %d\n", sim_nand_load(a1));
            s_sim_ready = 1;
        } else if (!strcmp(op, "check")) {
            printf("check %d\n", fw_debug_check());
        } else if (!strcmp(op, "quit")) {
            break;
        } else {
            printf("unknown: %s\n", op);
        }
        fflush(stdout);
    }
    return 0;
}
