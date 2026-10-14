/*
 * thermal.c - temperature sampling / throttle level
 *
 *  2018.11 mjlee   initial
 *  2019.02 mjlee   hysteresis 추가 (level 이 빠르게 오르내리는 문제)
 */
#include "thermal.h"
#include "fw_config.h"
#include "hal_temp.h"
#include "ftl.h"
#include "fw_log.h"

static struct {
    int32_t  cur_c;         /* 마지막 sample 값 */
    uint32_t level;
    uint32_t accum_ms;
} s_th;

static const int32_t s_th_enter[4] = { 0, THERM_L1_C, THERM_L2_C, THERM_L3_C };

void thermal_reset(void)
{
    memset(&s_th, 0, sizeof(s_th));
}

static uint32_t th_level_of(int32_t t)
{
    if (t >= THERM_L3_C) return 3;
    if (t >= THERM_L2_C) return 2;
    if (t >= THERM_L1_C) return 1;
    return 0;
}

void thermal_poll(void)
{
    uint32_t nl;

    s_th.cur_c = hal_temp_read();
    nl = th_level_of(s_th.cur_c);

    if (nl > s_th.level) {
        LOGW("therm", "level %u -> %u (%d C)", s_th.level, nl, s_th.cur_c);
        s_th.level = nl;
        g_cnt.throttle_events++;
        return;
    }
    /* 내려갈 때는 hysteresis 적용 */
    while (s_th.level > nl && s_th.cur_c < s_th_enter[s_th.level] - THERM_HYST_C) {
        s_th.level--;
        LOGI("therm", "level down -> %u (%d C)", s_th.level, s_th.cur_c);
    }
}

void thermal_tick(uint32_t ms)
{
    s_th.accum_ms += ms;
    if (s_th.accum_ms >= THERMAL_POLL_MS) {
        s_th.accum_ms = 0;
        thermal_poll();
    }
}

uint32_t thermal_level(void)
{
    return s_th.level;
}

int32_t thermal_cur_c(void)
{
    return s_th.cur_c;
}

uint16_t thermal_temp_k(void)
{
    int32_t k = s_th.cur_c + 273;

    if (k < 0)
        k = 0;
    return (uint16_t)k;
}
