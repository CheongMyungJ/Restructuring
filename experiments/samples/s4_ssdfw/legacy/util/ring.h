/*
 * ring.h - fixed size u32 ring buffer (single context, no locking)
 */
#ifndef RING_H
#define RING_H

#include <stdint.h>

typedef struct {
    uint32_t *buf;
    uint32_t  size;     /* number of slots */
    uint32_t  head;     /* next pop */
    uint32_t  tail;     /* next push */
    uint32_t  count;
} ring_t;

void ring_init(ring_t *r, uint32_t *buf, uint32_t size);
int  ring_push(ring_t *r, uint32_t v);      /* 0 ok, -1 full */
int  ring_pop(ring_t *r, uint32_t *v);      /* 0 ok, -1 empty */
int  ring_contains(const ring_t *r, uint32_t v);
static inline uint32_t ring_count(const ring_t *r) { return r->count; }

#endif
