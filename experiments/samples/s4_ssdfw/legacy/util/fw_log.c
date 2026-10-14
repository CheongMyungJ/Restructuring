/*
 * fw_log.c - log backend
 */
#include <stdarg.h>
#include <stdio.h>
#include "fw_log.h"
#include "fw_config.h"
#include "hal_timer.h"

uint32_t g_fw_dbg_level = FW_DBG_DEFAULT;

void fw_log_printf(int lvl, const char *mod, const char *fmt, ...)
{
    static const char *lv[] = { "-", "E", "W", "I", "T" };
    va_list ap;

#ifdef FW_ASIC
    /* asic: uart_ring_vprintf() - see platform/asic */
    (void)lv; (void)mod; (void)fmt; (void)ap; (void)lvl;
#else
    if (lvl < 0 || lvl > 4)
        lvl = 4;
    fprintf(stderr, "[%8u][%s][%s] ", (unsigned)hal_timer_ms(), lv[lvl], mod);
    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
    fputc('\n', stderr);
#endif
}
