/*
 * fw_log.h - debug log macros
 *   asic: UART ring buffer (asic_uart.c, 별도), sim: stderr
 *   level 은 vendor cmd 0xC1 로 런타임 변경 가능
 */
#ifndef FW_LOG_H
#define FW_LOG_H

#include <stdint.h>

#define LOG_ERR     1
#define LOG_WARN    2
#define LOG_INFO    3
#define LOG_TRACE   4

extern uint32_t g_fw_dbg_level;

void fw_log_printf(int lvl, const char *mod, const char *fmt, ...);

#define FW_LOG(lvl, mod, ...) \
    do { if ((uint32_t)(lvl) <= g_fw_dbg_level) fw_log_printf((lvl), (mod), __VA_ARGS__); } while (0)

#define LOGE(mod, ...)  FW_LOG(LOG_ERR,   mod, __VA_ARGS__)
#define LOGW(mod, ...)  FW_LOG(LOG_WARN,  mod, __VA_ARGS__)
#define LOGI(mod, ...)  FW_LOG(LOG_INFO,  mod, __VA_ARGS__)
#define LOGT(mod, ...)  FW_LOG(LOG_TRACE, mod, __VA_ARGS__)

/* 옛날 매크로 - 일부 코드에서 아직 사용 */
#define DBG_PRINT(...)  LOGI("dbg", __VA_ARGS__)

#endif
