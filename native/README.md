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
