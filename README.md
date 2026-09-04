# Price Comparison Tool

A small personal Python utility. It reads a local list of items, looks up a
reference price for each from public sources, fetches current active
fixed-price listings via an official marketplace API, and produces a ranked
table with three plain metrics per row:

- **Discount %** = (reference − listing price) / reference — the filter ("gate")
  that decides whether a row is shown (default 20; override per run);
- **Gross ROI %** = (reference − listing price) / listing price — shown as a column;
- **Spread $** = reference − listing price — raw difference, no fees included.

Reference prices are never invented: graded items use the median of completed
sales of the same item/grade; ungraded items use a public market price with a
labeled fallback. When a source fails, the row is counted in a "funnel"
summary instead of silently disappearing.

Single-user project. No paid services. The target list ships with the repo
(it is generated from a public catalog, see below); the notes on the comparison
method are kept locally and are not part of this published repository.

## Setup

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # Linux/macOS
```

Some features call an external marketplace API and need credentials provided as
environment variables (`EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`). Without them the
tool still runs in reference-price-only mode. Never commit credentials — see
[SECURITY.md](SECURITY.md).

The target list (`watchlist.yaml`) is **generated** by `build_watchlist.py`
and committed, so a fresh clone runs as-is. It is built from the catalog under
`src/catalog/`: 123 sets split into 12 fixed groups (`src/groups.py`), crossed
with the 100 most sought-after subjects (`iconic_pokemon.csv`), keeping only
rarity Holo Rare or higher and at most `--cap 30` items per set (ranked by
market price). Each item keeps an exact reference-page URL resolved by
name + number + set; an item with no reference page is left out and listed in
the script's report — a URL is never guessed. Regenerate only when the catalog
changes (the generated file says so in its header; do not edit it by hand):

```bash
python build_watchlist.py                        # all groups -> watchlist.yaml
python build_watchlist.py --groups 3-4 --cap 30  # a subset of groups
python build_watchlist.py --no-pc                # catalog only, no reference URLs (scan will not run on it)
```

`watchlist.example.yaml` remains as a template for a hand-made alternative
list (`python main.py --watchlist <file>`).

## Usage

```bash
python main.py --pricing-only                    # reference prices only (no credentials needed)
python main.py --list-groups                     # list the groups with their titles (no credentials needed)
python main.py --group 3                         # scan one group (default: discount >= 20%)
python main.py --group 3 --min-discount 10 --min-price 5 --include-raw --out results/last_scan_g3.json
                                                 # diagnostic run: lower gate, lower floor, ungraded included
python main.py --grades "PSA 10, CGC 10 Pristine"   # restrict this run to specific grades
python main.py --max-pages 2                     # fewer API pages per item (200 listings each)
```

A full run writes a JSON artifact with every evaluated row plus the funnel
counters (default `results/last_scan.json`, kept out of the repo). If the run
has to stop early (authentication failure or repeated API errors) the artifact
is marked `aborted: true` and the process exits with code 1. The report table
is then generated from that artifact by the summary tool:

```bash
python ebay_summary.py results/last_scan.json -o results/report-<date>.md
python ebay_summary.py results/last_scan.json -o results/report-<date>.md --sensitivity 10,15,20
```

It prints the markdown report (all rows, grouped by verdict, each row with the
listing link and the price-reference link, plus the funnel and a reference
coverage line) and saves it to `-o`. With `--sensitivity`, the highest
threshold is the operational one; the lower bands are printed as diagnostics
only, with a per-threshold count table.

`--group` takes a group spec — `N`, `N-M`, `1,3,10-12` or `all` (the 12
numbered groups; an unknown number is an error, never an empty scan) — or a
free-text group name from a hand-made list. Scanning one group per run keeps
the daily marketplace API quota in check (5,000 calls/day; roughly 1–3 calls
per item).

Run `python main.py --help` and `python ebay_summary.py --help` for all options.

## Tests

```bash
python -m pytest -q
```

The suite (493 tests) is offline — no network, no credentials; real payloads
and pages are stored under `tests/fixtures/` — and runs in CI on every push and
pull request.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
