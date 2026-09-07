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

/* Run `sims` simulations of the whole meet.
 *
 * Each simulation draws a time for every entry, then for each event awards
 * 5-3-1 to the teams of the three fastest drawn times (fewer places if the
 * event has fewer than three entries). expected[] receives each team's
 * average points per simulation.
 */
static void simulate_meet(Entry *entries, int n, int n_events, long sims,
                          double expected[2]) {
    double total[2] = {0,0};
    double times[MAX_ENTRIES];
    for (long s = 0; s < sims; s++) {
        for (int i = 0; i < n; i++) {
            times[i] = rand_normal(entries[i].mean, entries[i].std);
        }
        for (int j = 0; j < n_events; j++) {
            int fst_adr = -1;
            int sec_adr = -1;
            int thr_adr = -1;
            for (int k = 0; k < n; k++) {
                if (entries[k].event_id != j) continue;
                if (fst_adr == -1 || times[k] < times[fst_adr]) {
                    thr_adr = sec_adr;
                    sec_adr = fst_adr;
                    fst_adr = k;
                }
                else if (sec_adr == -1 || times[k] < times[sec_adr]) {
                    thr_adr = sec_adr;
                    sec_adr = k;
                }
                else if (thr_adr == -1 || times[k] < times[thr_adr]) {
                    thr_adr = k;
                }
            }
            if (fst_adr != -1) { total[entries[fst_adr].team] += 5; }
            if (sec_adr != -1) { total[entries[sec_adr].team] += 3; }
            if (thr_adr != -1) { total[entries[thr_adr].team] += 1; }
        }
    }
    expected[0] = total[0]/sims;
    expected[1] = total[1]/sims;
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
