# native — Monte Carlo scorer in C

A standalone C port of LaneLab's scoring core: read a meet's entries, simulate
it 10,000 times drawing each swim from Normal(mean, std), score 5-3-1 per
event, report expected points per team.

    make
    python3 export_meet_csv.py          # writes meet.csv from the demo league
    ./mc_score meet.csv 10000
    python3 reference_score.py meet.csv 10000   # pure-Python reference

The C and Python versions use different random generators, so their expected
points agree to within Monte Carlo noise (a few tenths of a point), not
digit-for-digit.

## Benchmark

10,000 simulations of the demo meet (237 entries, 40 events), Apple Silicon, `-O2`:

| implementation       | time   | sims/sec | team A | team B |
|----------------------|--------|----------|--------|--------|
| `reference_score.py` | 2.042s |    4,898 | 189.26 | 170.74 |
| `mc_score.c`         | 0.208s |   48,118 | 189.36 | 170.64 |

**9.8x faster.** The two versions use different random generators, so they agree
to within Monte Carlo noise (~0.1 points here) rather than digit-for-digit. As a
correctness check that does not depend on randomness, team A + team B must equal
exactly 360.00 on every run (40 events x 9 points).

Where the speedup comes from:

- Compiled to machine code — no per-operation interpreter dispatch.
- `Entry` is a flat 160-byte struct in a contiguous array, so the hot loop walks
  memory linearly and the prefetcher keeps up. The Python equivalent is a list of
  boxed tuples scattered across the heap.
- No allocation in the hot loop. The Python builds and sorts a fresh list for
  every event of every simulation.

Worth noting the C is not winning on algorithm: it scans all 237 entries per
event, while the Python groups by event first and scans about six. The 9.8x is
achieved while doing roughly 40x more comparisons. Pre-grouping the entries and
caching the discarded half of each Box-Muller pair should bring it under 0.1s,
but neither is implemented here.
