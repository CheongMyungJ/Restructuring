/*
 * sim_env.c - sim timer / temperature sensor
 *   시간은 test tool 이 sim_advance_ms() 로 진행시킨다 (deterministic)
 */
#include "hal_timer.h"
#include "hal_temp.h"
#include "sim.h"

static uint32_t s_ms;
static int32_t  s_temp_c = 40;

uint32_t hal_timer_ms(void)
{
    return s_ms;
}

int32_t hal_temp_read(void)
{
    return s_temp_c;
}

void sim_set_temp(int32_t c)
{
    s_temp_c = c;
}

void sim_advance_ms(uint32_t ms)
{
    s_ms += ms;
}
