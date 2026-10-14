/*
 * fw_types.h - common types / macros
 */
#ifndef FW_TYPES_H
#define FW_TYPES_H

#include <stdint.h>
#include <stddef.h>
#include <string.h>

#if defined(__GNUC__) || defined(__clang__)
#define FW_PACKED       __attribute__((packed))
#define FW_UNUSED       __attribute__((unused))
#else
#define FW_PACKED       /* armcc: use __packed */
#define FW_UNUSED
#endif

#ifndef MIN
#define MIN(a, b)       (((a) < (b)) ? (a) : (b))
#endif
#ifndef MAX
#define MAX(a, b)       (((a) > (b)) ? (a) : (b))
#endif
#define ARRAY_SIZE(x)   (sizeof(x) / sizeof((x)[0]))
#define DIV_ROUND_UP(a, b)  (((a) + (b) - 1) / (b))
#define BIT(n)          (1u << (n))

#define INVALID_U32     0xFFFFFFFFu
#define BLK_NONE        0xFFFFFFFFu

typedef uint8_t  u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;

#endif /* FW_TYPES_H */
