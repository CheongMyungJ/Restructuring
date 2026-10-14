/*
 * hal_temp.h - on-board temperature sensor
 *   returns degree Celsius (integer).  asic: I2C sensor @0x48, sim: settable.
 */
#ifndef HAL_TEMP_H
#define HAL_TEMP_H

#include <stdint.h>

int32_t hal_temp_read(void);

#endif
