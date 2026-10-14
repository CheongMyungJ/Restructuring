/*
 * ring.c - u32 ring buffer
 */
#include "ring.h"

void ring_init(ring_t *r, uint32_t *buf, uint32_t size)
{
    r->buf = buf;
    r->size = size;
    r->head = r->tail = r->count = 0;
}

int ring_push(ring_t *r, uint32_t v)
{
    if (r->count >= r->size)
        return -1;
    r->buf[r->tail] = v;
    r->tail = (r->tail + 1) % r->size;
    r->count++;
    return 0;
}

int ring_pop(ring_t *r, uint32_t *v)
{
    if (r->count == 0)
        return -1;
    *v = r->buf[r->head];
    r->head = (r->head + 1) % r->size;
    r->count--;
    return 0;
}

int ring_contains(const ring_t *r, uint32_t v)
{
    uint32_t i, idx;

    for (i = 0; i < r->count; i++) {
        idx = (r->head + i) % r->size;
        if (r->buf[idx] == v)
            return 1;
    }
    return 0;
}
