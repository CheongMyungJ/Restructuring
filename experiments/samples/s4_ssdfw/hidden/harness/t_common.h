/* t_common.h - hidden harness helpers */
#ifndef T_COMMON_H
#define T_COMMON_H

#include <stdint.h>
#include <setjmp.h>
#include "fw_api.h"
#include "hsim.h"

#define MAXLBA      32768
#define BLK         4096
#define MDTS        256

extern uint32_t g_cap;
extern jmp_buf  g_cut_jmp;

void     out(const char *key, const char *fmt, ...);
uint32_t rnd(void);
void     rnd_seed(uint32_t s);

uint16_t io_cmd(uint8_t opc, uint32_t nsid, uint64_t slba, uint32_t nlb,
                uint32_t c10, uint32_t c11, uint32_t c12, void *buf, uint32_t *cdw0);
uint16_t adm_cmd(uint8_t opc, uint32_t nsid, uint32_t c10, uint32_t c11, void *buf, uint32_t *cdw0);
int      boot(void);                    /* fw_init + capacity */
void     tick(uint32_t ms);
void     cut_handler(void);             /* longjmp(g_cut_jmp) */

void     make_block(uint8_t *p, uint32_t lba, uint32_t ver, uint32_t it, uint32_t ip, uint32_t id);
int64_t  block_ver(const uint8_t *p, uint32_t lba);    /* version, 0 = zeros, -1 corrupt */

/* host data model (per LBA versions) */
void     m_reset(void);
void     m_set_wt(int wt);
uint16_t m_write(uint64_t slba, uint32_t n, int fua);
uint16_t m_write_inj(uint32_t lba, uint32_t type, uint32_t param, uint32_t id);
uint16_t m_flush(void);
uint16_t m_trim(uint64_t slba, uint32_t n);
void     m_format(void);                /* all LBAs zero (durable after ckpt) */
uint32_t m_verify_exact(uint32_t lo, uint32_t hi);
uint32_t m_verify_durable(uint32_t lo, uint32_t hi);   /* adopts observed versions */
int64_t  m_read_ver(uint32_t lba, uint16_t *st);
uint32_t m_cur(uint32_t lba);
int      m_save(const char *path, const uint64_t *extra, int nextra);
int      m_load(const char *path, uint64_t *extra, int nextra);

typedef struct {
    uint16_t st;
    uint8_t  cw, spare, thr, used;
    uint16_t temp;
    uint64_t dur, duw, rcmd, wcmd, pc, poh, unsafe, media, errlog;
    uint8_t  raw[512];
} smart_t;

typedef struct {
    uint16_t st;
    uint32_t cdw0;
    uint32_t f[23];
    uint8_t  raw[512];
} c0_t;

enum { C0_SIG, C0_VER, C0_GC, C0_WL, C0_BAD, C0_GROWN, C0_RR, C0_REF, C0_RRREF, C0_RDREF,
       C0_FREE, C0_MINEC, C0_MAXEC, C0_AVGEC, C0_PFAIL, C0_EFAIL, C0_THERM, C0_THROT,
       C0_DIRTY, C0_CKPT, C0_NANDPROG, C0_FORMAT, C0_DBG };

int smart_get(smart_t *s);
int c0_get(c0_t *c);

#endif
