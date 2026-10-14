/* Black-box functional checks using only the public API. Prints CHECK lines. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "nfl/map.h"
#include "sim2.h"

#define NSEC 200
static int failures;
static char failmsg[256];
#define FAIL(...) do { if (!failures) snprintf(failmsg, sizeof failmsg, __VA_ARGS__); failures++; } while (0)

static uint32_t list[NSEC];
static void shuffle(uint32_t seed)
{
	uint32_t s = seed + 99;
	for (int i = 0; i < NSEC; i++) list[i] = (uint32_t)i;
	for (int i = NSEC - 1; i > 0; i--) {
		int j = (int)(sim2_rand(&s) % (uint32_t)i);
		uint32_t t = list[i]; list[i] = list[j]; list[j] = t;
	}
}

static int is_blank(const uint8_t *b, int n) { for (int i = 0; i < n; i++) if (b[i] != 0xff) return 0; return 1; }

static void reboot(struct nfl_map *m, uint8_t *pb, int gc)
{
	nfl_map_init(m, &sim2_nand, pb, (uint8_t)gc);
	nfl_map_resume(m, NULL);
}

static void run_seed(uint32_t seed, int nbad, int nbomb)
{
	const int PS = sim2_page_size();
	uint8_t *pb = malloc(PS), *buf = malloc(PS);
	struct nfl_map m;
	nfl_error_t err;
	int expect_count = 0;
	sim2_reset();
	sim2_inject_bad(seed, nbad);
	sim2_inject_timebombs(seed, nbomb, 20);
	reboot(&m, pb, 4);
	nfl_map_sync(&m, NULL);
	reboot(&m, pb, 4);
	if (nfl_map_size(&m) != 0) FAIL("seed %u: fresh size %u", seed, (unsigned)nfl_map_size(&m));

	shuffle(seed);
	for (int i = 0; i < NSEC; i++) {
		sim2_seq_gen(list[i] * 7u + 1u, buf, PS);
		if (nfl_map_write(&m, list[i], buf, &err) < 0) { FAIL("seed %u: write %u err %d", seed, list[i], err); goto out; }
	}
	expect_count = NSEC;
	if (nfl_map_size(&m) != (nfl_sector_t)expect_count) FAIL("seed %u: size after writes %u", seed, (unsigned)nfl_map_size(&m));
	nfl_map_sync(&m, NULL);
	reboot(&m, pb, 4);
	if (nfl_map_size(&m) != (nfl_sector_t)expect_count) FAIL("seed %u: size after resume %u", seed, (unsigned)nfl_map_size(&m));
	for (int i = 0; i < NSEC; i++) {
		if (nfl_map_read(&m, (nfl_sector_t)i, buf, &err) < 0) { FAIL("seed %u: read %d err %d", seed, i, err); goto out; }
		if (!sim2_seq_check((uint32_t)i * 7u + 1u, buf, PS)) FAIL("seed %u: data mismatch sector %d", seed, i);
	}
	/* rewrite half, trim half */
	shuffle(seed + 1000);
	for (int i = 0; i < NSEC; i += 2) {
		sim2_seq_gen(list[i] * 13u + 5u, buf, PS);
		if (nfl_map_write(&m, list[i], buf, &err) < 0) { FAIL("seed %u: rewrite err %d", seed, err); goto out; }
		if (nfl_map_trim(&m, list[i + 1], &err) < 0) { FAIL("seed %u: trim err %d", seed, err); goto out; }
	}
	expect_count = NSEC / 2;
	if (nfl_map_size(&m) != (nfl_sector_t)expect_count) FAIL("seed %u: size after trim %u", seed, (unsigned)nfl_map_size(&m));
	nfl_map_sync(&m, NULL);
	reboot(&m, pb, 4);
	for (int i = 0; i < NSEC; i += 2) {
		nfl_page_t loc;
		if (nfl_map_read(&m, list[i], buf, &err) < 0 || !sim2_seq_check(list[i] * 13u + 5u, buf, PS))
			FAIL("seed %u: rewritten sector %u bad", seed, list[i]);
		int r = nfl_map_find(&m, list[i + 1], &loc, &err);
		if (r >= 0 || err != NFL_E_NOT_FOUND) FAIL("seed %u: trimmed sector %u find r=%d err=%d", seed, list[i + 1], r, err);
		if (nfl_map_read(&m, list[i + 1], buf, &err) < 0 || !is_blank(buf, PS))
			FAIL("seed %u: trimmed sector %u not blank", seed, list[i + 1]);
	}
	/* copy_sector: mapped src */
	{
		nfl_sector_t src = list[0], dst = 5000 + seed % 7;
		if (nfl_map_copy_sector(&m, src, dst, &err) < 0) FAIL("seed %u: copy_sector err %d", seed, err);
		else if (nfl_map_read(&m, dst, buf, &err) < 0 || !sim2_seq_check(src * 13u + 5u, buf, PS))
			FAIL("seed %u: copy_sector data", seed);
		/* unmapped src trims dst */
		if (nfl_map_copy_sector(&m, list[1], dst, &err) < 0) FAIL("seed %u: copy_sector(unmapped) err %d", seed, err);
		else {
			nfl_page_t loc;
			if (nfl_map_find(&m, dst, &loc, &err) >= 0) FAIL("seed %u: copy_sector(unmapped) should trim dst", seed);
		}
		/* copy_page: copy physical page of list[2] to new sector */
		nfl_page_t loc;
		if (nfl_map_find(&m, list[2], &loc, &err) < 0) FAIL("seed %u: find for copy_page", seed);
		else if (nfl_map_copy_page(&m, loc, 6000, &err) < 0) FAIL("seed %u: copy_page err %d", seed, err);
		else if (nfl_map_read(&m, 6000, buf, &err) < 0 || !sim2_seq_check(list[2] * 13u + 5u, buf, PS))
			FAIL("seed %u: copy_page data", seed);
		if (nfl_map_size(&m) != (nfl_sector_t)(expect_count + 1)) FAIL("seed %u: size after copies %u", seed, (unsigned)nfl_map_size(&m));
	}
	/* gc steps must not lose data */
	for (int i = 0; i < 5; i++) if (nfl_map_gc(&m, &err) < 0) { FAIL("seed %u: gc err %d", seed, err); break; }
	nfl_map_sync(&m, NULL);
	reboot(&m, pb, 4);
	for (int i = 0; i < NSEC; i += 2)
		if (nfl_map_read(&m, list[i], buf, &err) < 0 || !sim2_seq_check(list[i] * 13u + 5u, buf, PS))
			FAIL("seed %u: after gc sector %u bad", seed, list[i]);
	/* clear */
	nfl_map_clear(&m);
	if (nfl_map_size(&m) != 0) FAIL("seed %u: size after clear", seed);
	nfl_map_sync(&m, NULL);
	reboot(&m, pb, 4);
	if (nfl_map_size(&m) != 0) FAIL("seed %u: size after clear+resume %u", seed, (unsigned)nfl_map_size(&m));
	if (nfl_map_read(&m, list[0], buf, &err) < 0 || !is_blank(buf, PS)) FAIL("seed %u: read after clear not blank", seed);
out:
	free(pb); free(buf);
}

static void check(const char *name, void (*fn)(void))
{
	failures = 0; failmsg[0] = 0;
	fn();
	printf("CHECK %s %s %s\n", name, failures ? "FAIL" : "PASS", failmsg);
	fflush(stdout);
}

static void t_basic(void) { sim2_setup(9, 3, 113); for (uint32_t s = 0; s < 40; s++) { run_seed(s, 10, 30); if (failures) return; } }
static void t_geom2(void) { sim2_setup(11, 5, 96); for (uint32_t s = 100; s < 110; s++) { run_seed(s, 3, 5); if (failures) return; } }

static void t_unsynced_lost(void)
{
	/* After sync + power loss, synced data must survive and resume must succeed. */
	sim2_setup(9, 3, 113);
	const int PS = sim2_page_size();
	uint8_t *pb = malloc(PS), *buf = malloc(PS);
	struct nfl_map m; nfl_error_t err;
	sim2_reset();
	reboot(&m, pb, 4);
	for (int i = 0; i < 50; i++) { sim2_seq_gen(i + 77u, buf, PS); nfl_map_write(&m, i, buf, &err); }
	nfl_map_sync(&m, NULL);
	for (int i = 0; i < 3; i++) { sim2_seq_gen(i + 999u, buf, PS); nfl_map_write(&m, i, buf, &err); }
	/* power loss: no sync */
	reboot(&m, pb, 4);
	for (int i = 3; i < 50; i++)
		if (nfl_map_read(&m, i, buf, &err) < 0 || !sim2_seq_check(i + 77u, buf, PS)) { FAIL("synced sector %d lost", i); break; }
	for (int i = 0; i < 3; i++) {
		if (nfl_map_read(&m, i, buf, &err) < 0) { FAIL("read %d", i); break; }
		if (!sim2_seq_check(i + 77u, buf, PS) && !sim2_seq_check(i + 999u, buf, PS)) { FAIL("sector %d neither old nor new", i); break; }
	}
	free(pb); free(buf);
}

static void t_resume_blank(void)
{
	sim2_setup(9, 3, 64);
	sim2_reset();
	const int PS = sim2_page_size();
	uint8_t *pb = malloc(PS);
	struct nfl_map m; nfl_error_t err = NFL_E_NONE;
	nfl_map_init(&m, &sim2_nand, pb, 4);
	int r = nfl_map_resume(&m, &err);
	if (r != -1) FAIL("resume on blank chip returned %d (expected -1)", r);
	if (nfl_map_size(&m) != 0) FAIL("size after failed resume");
	if (nfl_map_capacity(&m) == 0) FAIL("capacity 0 after failed resume");
	free(pb);
}

static void t_errors(void)
{
	sim2_setup(9, 3, 113);
	sim2_reset();
	const int PS = sim2_page_size();
	uint8_t *pb = malloc(PS), *buf = malloc(PS);
	struct nfl_map m; nfl_error_t err;
	reboot(&m, pb, 4);
	nfl_page_t loc;
	err = NFL_E_NONE;
	if (nfl_map_find(&m, 12345, &loc, &err) != -1 || err != NFL_E_NOT_FOUND) FAIL("find on empty map");
	if (nfl_map_read(&m, 12345, buf, &err) < 0 || !is_blank(buf, PS)) FAIL("read unmapped not blank");
	if (nfl_map_trim(&m, 4242, &err) < 0) FAIL("trim unmapped should succeed");
	if (strcmp(nfl_strerror(NFL_E_NOT_FOUND), nfl_strerror(NFL_E_MAP_FULL)) == 0) FAIL("strerror not distinct");
	free(pb); free(buf);
}

int main(void)
{
	check("api_basic_multi_seed", t_basic);
	check("api_other_geometry", t_geom2);
	check("api_synced_survive_power_loss", t_unsynced_lost);
	check("api_resume_blank_chip", t_resume_blank);
	check("api_error_semantics", t_errors);
	return 0;
}
