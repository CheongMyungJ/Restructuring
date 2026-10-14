/*
 * bitops.h - byte order / bit helpers
 *
 * 주의: on-NAND 구조체는 little-endian (ARM LE / x86 LE 동일) 이므로
 *       memcpy 로 그대로 저장한다.  host 버퍼 직렬화에만 아래 매크로 사용.
 */
#ifndef BITOPS_H
#define BITOPS_H

#include <stdint.h>

static inline void put_le16(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8);
}

static inline void put_le32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8);
    p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24);
}

static inline void put_le64(uint8_t *p, uint64_t v)
{
    put_le32(p, (uint32_t)v);
    put_le32(p + 4, (uint32_t)(v >> 32));
}

/* 128bit LE field (SMART counters) - upper 64 bits always 0 */
static inline void put_le128(uint8_t *p, uint64_t v)
{
    int i;
    put_le64(p, v);
    for (i = 8; i < 16; i++)
        p[i] = 0;
}

static inline uint32_t get_le32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static inline void put_be32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)(v >> 24); p[1] = (uint8_t)(v >> 16);
    p[2] = (uint8_t)(v >> 8);  p[3] = (uint8_t)v;
}

static inline uint32_t get_be32(const uint8_t *p)
{
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | (uint32_t)p[3];
}

static inline int popcount32(uint32_t v)
{
    int n = 0;
    while (v) { v &= v - 1; n++; }
    return n;
}

#endif /* BITOPS_H */
