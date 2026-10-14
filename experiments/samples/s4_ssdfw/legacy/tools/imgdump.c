/*
 * imgdump.c - dump superblock / metadata pages of a sim NAND image
 *   usage: imgdump <image> [-v]
 *   2018.10 sypark
 */
#include <stdio.h>
#include <string.h>
#include "hal_nand.h"
#include "fw_config.h"
#include "nand_profile.h"
#include "meta_format.h"
#include "crc32.h"
#include "sim.h"

static const char *ptype(uint8_t t)
{
    switch (t) {
    case PG_TYPE_USER: return "USER";
    case PG_TYPE_SB:   return "SB";
    case PG_TYPE_CKPT: return "CKPT";
    case PG_TYPE_JRNL: return "JRNL";
    default:           return "?";
    }
}

int main(int argc, char **argv)
{
    const uint8_t *d, *s;
    const spare_hdr_t *sp;
    const sb_t *sb;
    const jrnl_hdr_t *jh;
    uint32_t b, p, nuser = 0, nblank = 0;
    int verbose = (argc > 2 && !strcmp(argv[2], "-v"));

    if (argc < 2) {
        fprintf(stderr, "usage: %s <image> [-v]\n", argv[0]);
        return 1;
    }
    if (sim_nand_load(argv[1]) != 0) {
        fprintf(stderr, "cannot load %s\n", argv[1]);
        return 1;
    }
    for (b = 0; b < 2; b++) {
        d = sim_nand_page_data(b, 0);
        if (!d) { printf("SB%u: blank\n", b); continue; }
        sb = (const sb_t *)d;
        printf("SB%u: magic %08x/%08x fmt %04x type %u op %u geo %ux%u cap %u sn '%.20s' fw '%.8s' bad %u crc %s\n",
               b, sb->magic0, sb->magic1, sb->fmt_version, sb->nand_type, sb->op_percent,
               sb->num_blocks, sb->pages_per_block, sb->capacity_lbas, sb->serial, sb->fw_rev,
               sb->factory_bad, sb->crc == crc32_calc(sb, sizeof(*sb) - 4) ? "ok" : "BAD");
    }
    for (b = META_START; b < META_START + META_BLOCKS; b++) {
        for (p = 0; p < NAND_PAGES_PER_BLK; p++) {
            if (sim_nand_page_state(b, p) == 0)
                break;
            s = sim_nand_page_spare(b, p);
            d = sim_nand_page_data(b, p);
            sp = (const spare_hdr_t *)s;
            if (sim_nand_page_state(b, p) == 2) {
                printf("META %3u/%2u TORN\n", b, p);
                continue;
            }
            printf("META %3u/%2u %-4s seq %6u base %6u part %u/%u cnt %u flags %x\n",
                   b, p, ptype(sp->type), sp->seq, sp->u.m.base_seq, sp->u.m.part,
                   sp->u.m.nparts, sp->u.m.count, sp->flags);
            if (verbose && sp->type == PG_TYPE_JRNL) {
                jh = (const jrnl_hdr_t *)d;
                printf("     pc %llu unsafe %llu duw %llu gc %u\n",
                       (unsigned long long)jh->p.power_cycles,
                       (unsigned long long)jh->p.unsafe_shutdowns,
                       (unsigned long long)jh->p.du_written_raw, jh->p.gc_count);
            }
        }
    }
    for (b = SYS_BLOCKS; b < NAND_BLOCKS; b++)
        for (p = 0; p < NAND_PAGES_PER_BLK; p++) {
            if (sim_nand_page_state(b, p) == 0) nblank++;
            else nuser++;
        }
    printf("user area: %u programmed pages, %u erased pages\n", nuser, nblank);
    return 0;
}
