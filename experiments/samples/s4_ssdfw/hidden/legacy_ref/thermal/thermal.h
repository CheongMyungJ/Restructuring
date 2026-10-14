/*
 * thermal.h - thermal throttling
 *   level 0: normal
 *   level 1: >= THERM_L1_C  background(idle) GC 중지
 *   level 2: >= THERM_L2_C  + write cache 사용량 1/2 로 제한
 *   level 3: >= THERM_L3_C  + write cache 미사용 (write-through)
 */
#ifndef THERMAL_H
#define THERMAL_H

#include <stdint.h>

void     thermal_reset(void);
void     thermal_poll(void);
void     thermal_tick(uint32_t ms);
uint32_t thermal_level(void);
int32_t  thermal_cur_c(void);
uint16_t thermal_temp_k(void);

#endif
