/* mc_score.c — standalone Monte Carlo meet scorer (C port of LaneLab's core).
 *
 * Reads a CSV of entries (team,swimmer,event,mean,std), simulates the meet
 * N times drawing each swim from Normal(mean, std), scores 5-3-1 per event,
 * and prints each team's expected points.
 *
 * Build:  make        Run:  ./mc_score meet.csv 10000
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>

#define MAX_ENTRIES 512
#define NAME_LEN    64

typedef struct {
    int    team;              /* 0 or 1 */
    char   swimmer[NAME_LEN];
    char   event[NAME_LEN];
    double mean;              /* seconds */
    double std;               /* seconds */
    int    event_id;          /* filled in by index_events() */
} Entry;

/* ---------- provided helpers (not the learning target) ------------------- */

/* One draw from Normal(mu, sigma) via Box-Muller. */
static double rand_normal(double mu, double sigma) {
    double u1 = (rand() + 1.0) / ((double)RAND_MAX + 2.0);
    double u2 = (rand() + 1.0) / ((double)RAND_MAX + 2.0);
    return mu + sigma * sqrt(-2.0 * log(u1)) * cos(2.0 * M_PI * u2);
}

/* Load entries from CSV: team,swimmer,event,mean,std (no header). */
static int load_csv(const char *path, Entry *entries, int max) {
    FILE *f = fopen(path, "r");
    if (!f) { perror(path); return -1; }
    char line[256];
    int n = 0;
    while (n < max && fgets(line, sizeof line, f)) {
        Entry *e = &entries[n];
        if (sscanf(line, "%d,%63[^,],%63[^,],%lf,%lf",
                   &e->team, e->swimmer, e->event, &e->mean, &e->std) == 5)
            n++;
    }
    fclose(f);
    return n;
}

/* Assign each entry an event_id (0..n_events-1); returns n_events. */
static int index_events(Entry *entries, int n) {
    int n_events = 0;
    for (int i = 0; i < n; i++) {
        int found = -1;
        for (int j = 0; j < i; j++)
            if (strcmp(entries[j].event, entries[i].event) == 0) { found = entries[j].event_id; break; }
        entries[i].event_id = (found >= 0) ? found : n_events++;
    }
    return n_events;
}

/* ---------- YOUR PART ----------------------------------------------------- */
/*
 * simulate_meet: run `sims` simulations of the whole meet.
 *
 * For ONE simulation:
 *   1. For every entry, draw a time: rand_normal(e->mean, e->std).
 *   2. For every event (use event_id to group), find the three fastest
 *      drawn times across BOTH teams in that event.
 *   3. Award 5 points for 1st, 3 for 2nd, 1 for 3rd to the entry's team.
 *      (Events with fewer than 3 entries award only the places that exist.)
 *
 * Accumulate each team's points over all simulations, then divide by `sims`
 * to fill expected[0] and expected[1].
 *
 * Suggested shape: a times[MAX_ENTRIES] array per simulation, then for each
 * event a small pass to find its top three (no need to sort everything —
 * three linear scans, or one scan tracking best/second/third, both work).
 * Keep it simple first; make it fast after it agrees with the reference.
 */
static void simulate_meet(Entry *entries, int n, int n_events, long sims,
                          double expected[2]) {
    (void)entries; (void)n; (void)n_events; (void)sims;   /* TODO: remove */
    expected[0] = 0.0;   /* TODO: implement */
    expected[1] = 0.0;
}

/* ---------- main / timing harness ---------------------------------------- */

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: %s <meet.csv> <n_sims> [seed]\n", argv[0]);
        return 1;
    }
    srand(argc > 3 ? (unsigned)atoi(argv[3]) : 42);

    static Entry entries[MAX_ENTRIES];
    int n = load_csv(argv[1], entries, MAX_ENTRIES);
    if (n <= 0) { fprintf(stderr, "no entries loaded\n"); return 1; }
    int n_events = index_events(entries, n);
    long sims = atol(argv[2]);

    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    double expected[2];
    simulate_meet(entries, n, n_events, sims, expected);
    clock_gettime(CLOCK_MONOTONIC, &t1);
    double secs = (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) / 1e9;

    printf("entries: %d  events: %d  sims: %ld\n", n, n_events, sims);
    printf("expected points  team A: %.2f   team B: %.2f\n", expected[0], expected[1]);
    printf("time: %.3fs  (%.0f sims/sec)\n", secs, sims / (secs > 0 ? secs : 1e-9));
    return 0;
}
