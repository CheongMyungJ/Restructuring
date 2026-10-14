/*
 * smart.h - SMART / Health Information (log page 0x02)
 */
#ifndef SMART_H
#define SMART_H

#include <stdint.h>

#define SMART_LOG_SIZE      512

#define CW_SPARE            0x01
#define CW_TEMPERATURE      0x02
#define CW_RELIABILITY      0x04
#define CW_READ_ONLY        0x08
#define CW_VWC_BACKUP       0x10

void    smart_build_log(uint8_t *log);
uint8_t smart_critical_warning(void);
uint8_t smart_percent_used(void);
uint8_t smart_avail_spare(void);

#endif
