/*
 * crc32.c - table driven CRC32 (IEEE)
 *   asic 에서는 HW CRC 엔진을 쓰는 버전이 있었으나 (crc32_hw.c, 삭제됨)
 *   메타데이터 양이 적어서 SW 테이블로 통일. 2017.01 hwchoi
 */
#include "crc32.h"

static uint32_t s_crc_tab[256];
static int      s_crc_init;

static void crc32_mktab(void)
{
    uint32_t i, j, c;

    for (i = 0; i < 256; i++) {
        c = i;
        for (j = 0; j < 8; j++)
            c = (c & 1) ? (0xEDB88320u ^ (c >> 1)) : (c >> 1);
        s_crc_tab[i] = c;
    }
    s_crc_init = 1;
}

uint32_t crc32_update(uint32_t crc, const void *buf, size_t len)
{
    const uint8_t *p = (const uint8_t *)buf;

    if (!s_crc_init)
        crc32_mktab();
    while (len--)
        crc = s_crc_tab[(crc ^ *p++) & 0xFF] ^ (crc >> 8);
    return crc;
}

uint32_t crc32_calc(const void *buf, size_t len)
{
    return crc32_update(0xFFFFFFFFu, buf, len) ^ 0xFFFFFFFFu;
}
