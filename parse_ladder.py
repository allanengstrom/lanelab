#!/usr/bin/env python3
"""
Parse a HY-TEK Team Manager 'Individual Top Times' (ladder) PDF into CSV.

Usage:
    python3 parse_ladder.py <input.pdf> [output.csv]

Output columns: Name, Gender, AgeGroup, Stroke, Distance, Time, Date, Source
  - Date in YYYY-MM-DD format
  - Time in decimal seconds (parses 'mm:ss.xx' too)
  - Source: TimeTrial / AMeet / BMeet / Other

Skips IM events (we only model free/back/breast/fly).
"""

import csv
import re
import sys
import os

try:
    import pymupdf
except ImportError:
    try:
        # Older versions packaged as `fitz`
        import fitz as pymupdf
    except ImportError:
        print("Missing dependency: pymupdf. Install with:\n  pip3 install pymupdf",
              file=sys.stderr)
        sys.exit(1)

# Header lines like:
#   Girls 8 & Under 25 Free
#   Girls 9-10 50 Free
#   Girls 11-12 50 Back
#   Girls 13-14 100 IM
#   Girls 50 Free      (= 15-18)
#   Boys 50 Back       (= 15-18)
HDR_AGED = re.compile(
    r"^\s*(Boys|Girls)\s+(8\s*&\s*Under|9-10|11-12|13-14)\s+(\d+)\s+(Free|Back|Breast|Fly|IM)\s*$"
)
HDR_OLD = re.compile(
    r"^\s*(Boys|Girls)\s+(\d+)\s+(Free|Back|Breast|Fly|IM)\s*$"
)

# Data rows like:
#    1 19.32 S F Harper Vance 8 6/16/2025 2025-06-16 B-Meet LP@SHB
#    8 1:02.40 S F Sylvia Trask 9 6/7/2025 SHBR Time Trials
# Pattern: rank time P/F/S name age date... meet
ROW_RE = re.compile(
    r"^\s*\d+\s+([\d:.]+)\s+S\s+F\s+"
    r"(.+?)\s+(\d+)\s+"             # name + age (greedy on name, then age)
    r"(\d{1,2}/\d{1,2}/\d{4})\s+"    # date m/d/yyyy
    r"(.+?)\s*$"                     # rest = meet
)

# Data rows in the newer "no date" format used by HY-TEK's two-column ladder:
#    1 19.59 S F Maren Holloway 8
# Pattern: rank time S F name age
ROW_RE_NODATE = re.compile(
    r"^\s*\d+\s+([\d:.]+)\s+S\s+F\s+"
    r"(.+?)\s+(\d+)\s*$"             # name + age (greedy on name, then age)
)

# Report-date in the header line like:
#    Licensed To: Sleepy Hollow Bath and Racquet Club HY-TEK's TEAM MANAGER 8.0 6/9/2025 Page 1
REPORT_DATE_RE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b\s+Page\s+\d+")

AGE_MAP = {"8 & Under": "8U", "8 &  Under": "8U",
           "9-10": "9-10", "11-12": "11-12", "13-14": "13-14"}
STROKES_OK = {"Free", "Back", "Breast", "Fly"}


def parse_time(s):
    s = s.strip()
    if ":" in s:
        mins, rest = s.split(":", 1)
        return float(mins) * 60.0 + float(rest)
    return float(s)


def parse_date(s):
    m, d, y = s.split("/")
    return f"{y}-{int(m):02d}-{int(d):02d}"


def classify_source(meet_str):
    s = meet_str.lower()
    if "time trial" in s:
        return "TimeTrial"
    if "a-meet" in s or "a meet" in s or "nvsl a" in s:
        return "AMeet"
    if "b-meet" in s or "b meet" in s:
        return "BMeet"
    return "Other"


# ── SwimTopia "Best Times" report format (2026+) ───────────────────────────────
# Layout: a section header per gender+age ("Girls 8 & Under"), a column-label row
# (Name / Time / Event / Date / Swim Meet), then each entry as five consecutive
# lines: "Last, First (age)" / time / "25 Freestyle" / MM/DD/YY / meet name.
# SwimTopia labels the 15-18 sections "Women 15-18" / "Men 15-18" (not Girls/Boys);
# without this they're unparsed and those swimmers inherit the prior section's
# age/gender (e.g. a 15yo girl tagged Boys 13-14).
HDR_ST = re.compile(r"^(Girls|Boys|Women|Men)\s+(8 & Under|9-10|11-12|13-14|15-18|15 & Over)\s*$")
ST_GENDER = {"Girls": "Girls", "Boys": "Boys", "Women": "Girls", "Men": "Boys"}
EVENT_ST = re.compile(r"^(\d+)\s+(Freestyle|Backstroke|Breaststroke|Butterfly)\s*$")
NAME_ST = re.compile(r"^[A-Za-z][\w'’.\- ]*,\s+\S.*\(\d+\)\s*$")
DATE_ST = re.compile(r"^(\d{2})/(\d{2})/(\d{2})\s*$")
ST_AGE = {"8 & Under": "8U", "9-10": "9-10", "11-12": "11-12",
          "13-14": "13-14", "15-18": "15-18", "15 & Over": "15-18"}
ST_STROKE = {"Freestyle": "free", "Backstroke": "back",
             "Breaststroke": "breast", "Butterfly": "fly"}
ST_LABELS = {"Name", "Time", "Event", "Date", "Swim Meet"}

# Some PDF exports render "fl"/"fi" etc. as single typographic ligature glyphs
# (e.g. "Butterﬂy" with U+FB02). Those don't match our stroke names, so every
# such event would be silently dropped. Expand them back to plain ASCII at text
# extraction so matching works everywhere (event labels, names, meet names).
_LIGATURES = {
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl",
    "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "ft", "ﬆ": "st",
}
def _fix_ligatures(s):
    if not s:
        return s
    for glyph, repl in _LIGATURES.items():
        if glyph in s:
            s = s.replace(glyph, repl)
    return s


def _st_name(s):
    """'Navarro Quinn, Asha (8)' -> 'Asha Navarro Quinn'."""
    s = re.sub(r"\s*\(\d+\)\s*$", "", s).strip()
    if "," in s:
        last, first = s.split(",", 1)
        return f"{first.strip()} {last.strip()}".strip()
    return s


def _st_date(s):
    m = DATE_ST.match(s)
    if not m:
        return None
    mm, dd, yy = m.groups()
    return f"20{yy}-{mm}-{dd}"


def parse_swimtopia(doc):
    """Parse a SwimTopia Best-Times PDF -> list of entry dicts (same schema as
    the HY-TEK path). Robust to stray lines: only emits a row when the five
    consecutive fields all validate (name, time, event, date, meet)."""
    lines = []
    for page in doc:
        lines += [_fix_ligatures(l.strip()) for l in page.get_text().split("\n") if l.strip()]
    out = []
    gender = age = None
    i = 0
    while i < len(lines):
        l = lines[i]
        h = HDR_ST.match(l)
        if h:
            gender, age = ST_GENDER[h.group(1)], ST_AGE.get(h.group(2))
            i += 1
            continue
        if l in ST_LABELS:
            i += 1
            continue
        if gender and age and NAME_ST.match(l) and i + 4 < len(lines):
            name_s, time_s, ev_s, date_s, meet_s = lines[i:i + 5]
            ev = EVENT_ST.match(ev_s)
            dt = _st_date(date_s)
            try:
                t = parse_time(time_s)
            except Exception:
                t = None
            if ev and dt and t is not None:
                out.append({
                    "Name":     _st_name(name_s),
                    "Gender":   gender,
                    "AgeGroup": age,
                    "Stroke":   ST_STROKE[ev.group(2)],
                    "Distance": int(ev.group(1)),
                    "Time":     t,
                    "Date":     dt,
                    "Source":   classify_source(meet_s),
                })
                i += 5
                continue
        i += 1
    return out


def _detect_columns(words, page_width):
    """
    Decide if the page has a two-column layout. Returns the split x-coordinate
    if so, else None.

    Gating signal: count the number of y-rows with more than 12 words. A
    two-column HY-TEK data row has ~14 words (two ranks, two times, two
    S/F pairs, two names+ages); a single-column data row has ~11 words.
    If 5+ rows clear the 12-word bar, treat as two-column and pick the
    midpoint empty band as the split.
    """
    if not words:
        return None

    # 1. Gating signal: count rows with >12 words
    from collections import Counter
    rows_per_y = {}
    for w in words:
        x0, y0, *_ = w
        y_key = round(y0 / 2) * 2
        rows_per_y.setdefault(y_key, []).append(x0)
    wide_rows = sum(1 for xs in rows_per_y.values() if len(xs) > 12)
    if wide_rows < 5:
        return None  # single-column layout

    # 2. Find the empty band closest to page midpoint
    xs = Counter()
    for w in words:
        x0 = w[0]
        if x0 < 20 or x0 > page_width - 20: continue
        xs[round(x0 / 5) * 5] += 1
    if not xs: return None

    mid_lo, mid_hi = page_width * 0.30, page_width * 0.60
    page_mid = page_width / 2
    sorted_x = sorted(xs.keys())
    candidates = []
    for i in range(len(sorted_x) - 1):
        x1, x2 = sorted_x[i], sorted_x[i + 1]
        gap = x2 - x1
        if gap < 25: continue
        center = (x1 + x2) / 2
        if not (mid_lo <= center <= mid_hi): continue
        candidates.append((abs(center - page_mid), gap, center))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][2]


def _page_lines(page, y_tolerance=2.0, column_split=None):
    """
    Extract lines from a PDF page by grouping words with similar y-coordinates.
    pymupdf's default get_text() reads cells column-by-column for layout PDFs
    like HY-TEK; this reassembles them into proper rows.

    If column_split is set (an x-coordinate), returns (left_lines, right_lines)
    — words to the left and right of the split are kept as separate independent
    line streams. Otherwise returns a single flat list of lines.
    """
    words = page.get_text("words")
    if not words:
        return ([], []) if column_split is not None else []

    if column_split is None:
        # Single-column behavior (backward-compat for old PDFs)
        rows = {}
        for w in words:
            x0, y0, _x1, _y1, text, *_ = w
            y_key = round(y0 / y_tolerance) * y_tolerance
            rows.setdefault(y_key, []).append((x0, text))
        lines = []
        for y in sorted(rows.keys()):
            line = _fix_ligatures(" ".join(t for _, t in sorted(rows[y])))
            lines.append(line)
        return lines

    # Two-column: split each row at column_split, build two independent streams
    left_rows, right_rows = {}, {}
    for w in words:
        x0, y0, _x1, _y1, text, *_ = w
        y_key = round(y0 / y_tolerance) * y_tolerance
        bucket = left_rows if x0 < column_split else right_rows
        bucket.setdefault(y_key, []).append((x0, text))
    left_lines = [
        _fix_ligatures(" ".join(t for _, t in sorted(left_rows[y])))
        for y in sorted(left_rows.keys())
    ]
    right_lines = [
        _fix_ligatures(" ".join(t for _, t in sorted(right_rows[y])))
        for y in sorted(right_rows.keys())
    ]
    return (left_lines, right_lines)


def _process_lines(lines, default_date, default_source="Ladder"):
    """Process a single column's worth of lines, returning parsed time entries."""
    out = []
    cur_gender, cur_age, cur_dist, cur_stroke = None, None, None, None
    for line in lines:
        line = line.rstrip()
        # Try header forms
        m = HDR_AGED.match(line)
        if m:
            cur_gender = m.group(1)
            cur_age    = AGE_MAP.get(re.sub(r"\s+", " ", m.group(2)).strip(), m.group(2))
            cur_dist   = int(m.group(3))
            cur_stroke = m.group(4)
            continue
        m = HDR_OLD.match(line)
        if m and cur_gender != m.group(1):  # avoid colliding with old header
            cur_gender = m.group(1)
            cur_age    = "15-18"
            cur_dist   = int(m.group(2))
            cur_stroke = m.group(3)
            continue
        # Handle "Girls 50 Free" / "Boys 50 Back" (no age = 15-18)
        m2 = re.match(r"^\s*(Boys|Girls)\s+(\d+)\s+(Free|Back|Breast|Fly|IM)\s*$", line)
        if m2:
            cur_gender = m2.group(1)
            cur_age    = "15-18"
            cur_dist   = int(m2.group(2))
            cur_stroke = m2.group(3)
            continue

        if not (cur_stroke and cur_stroke in STROKES_OK):
            continue

        # Try data row WITH date/meet (old format)
        m = ROW_RE.match(line)
        if m:
            time_str, name, age, date, meet = m.groups()
            out.append({
                "Name":     name.strip(),
                "Gender":   cur_gender,
                "AgeGroup": cur_age,
                "Stroke":   cur_stroke.lower(),
                "Distance": cur_dist,
                "Time":     parse_time(time_str),
                "Date":     parse_date(date),
                "Source":   classify_source(meet),
            })
            continue

        # Try data row WITHOUT date/meet (new HY-TEK format)
        m = ROW_RE_NODATE.match(line)
        if m:
            time_str, name, age = m.groups()
            out.append({
                "Name":     name.strip(),
                "Gender":   cur_gender,
                "AgeGroup": cur_age,
                "Stroke":   cur_stroke.lower(),
                "Distance": cur_dist,
                "Time":     parse_time(time_str),
                "Date":     default_date,
                "Source":   default_source,
            })
    return out


def parse_pdf(pdf_path):
    """Returns list of dicts, one per parsed time entry.

    Supports both old single-column HY-TEK exports (with date/meet columns)
    and the newer two-column format (no date/meet — uses the PDF's report
    date as the entry date and "Ladder" as the source).
    """
    rows = []
    doc = pymupdf.open(pdf_path)
    try:
        # Auto-detect the report format from the page-1 header.
        head = ((doc[0].get_text("text") if len(doc) else "") or "")[:600].lower()
        if "swimtopia" in head or "best times" in head:
            return parse_swimtopia(doc)
        # Otherwise: HY-TEK Team Manager 'Individual Top Times'.
        # Extract report date from the header of page 1 for date-less rows
        default_date = None
        if len(doc) > 0:
            first_text = doc[0].get_text("text") or ""
            mhdr = REPORT_DATE_RE.search(first_text)
            if mhdr:
                default_date = parse_date(mhdr.group(1))
        if default_date is None:
            import datetime as _dt
            default_date = _dt.date.today().isoformat()

        for page in doc:
            page_width = page.rect.width
            words = page.get_text("words")
            split_x = _detect_columns(words, page_width)
            if split_x is not None:
                left, right = _page_lines(page, column_split=split_x)
                rows.extend(_process_lines(left, default_date))
                rows.extend(_process_lines(right, default_date))
            else:
                rows.extend(_process_lines(_page_lines(page), default_date))
    finally:
        doc.close()
    return rows


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    pdf_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) >= 3 else os.path.splitext(pdf_path)[0] + ".csv"

    rows = parse_pdf(pdf_path)
    if not rows:
        print("No data rows parsed. Check the PDF format.", file=sys.stderr)
        sys.exit(2)

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "Name", "Gender", "AgeGroup", "Stroke", "Distance", "Time", "Date", "Source",
        ])
        writer.writeheader()
        writer.writerows(rows)

    # Quick summary
    swimmers = {r["Name"] for r in rows}
    events   = {(r["AgeGroup"], r["Gender"], r["Stroke"], r["Distance"]) for r in rows}
    sources  = {}
    for r in rows:
        sources[r["Source"]] = sources.get(r["Source"], 0) + 1
    print(f"Parsed {len(rows)} entries → {out_path}")
    print(f"  Distinct swimmers: {len(swimmers)}")
    print(f"  Distinct events:   {len(events)}")
    print(f"  By source: {sources}")


if __name__ == "__main__":
    main()
