/*
 * hal_timer.h - free running millisecond timer
 *   asic: TIMER0 (1kHz tick), sim: host side clock
 */
#ifndef HAL_TIMER_H
#define HAL_TIMER_H

#include <stdint.h>

uint32_t hal_timer_ms(void);

#endif
