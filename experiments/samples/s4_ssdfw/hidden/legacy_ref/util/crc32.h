#ifndef CRC32_H
#define CRC32_H

#include <stdint.h>
#include <stddef.h>

/* IEEE 802.3 (reflected, poly 0xEDB88320), init 0xFFFFFFFF, final xor */
uint32_t crc32_calc(const void *buf, size_t len);
uint32_t crc32_update(uint32_t crc, const void *buf, size_t len);   /* raw, no init/xor */

#endif
