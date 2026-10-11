# Casino Bonus Scraper

Screening task for AIBOOST — pulls sweepstakes casino bonus data from one public
source, extracts structured fields with an LLM, and renders them on a
mobile-friendly page.

## Live page

PASTE_YOUR_VERCEL_URL_HERE

## What it does

1. Fetches `https://www.covers.com/casino/sweepstakes` (public comparison page).
2. Locates the review block for each of 3 target casinos.
3. Sends each block to Google Gemini (`gemini-flash-latest`) with a strict
   JSON-schema prompt.
4. Validates the response with Pydantic.
5. Looks up an Internet Archive (Wayback Machine) snapshot of the source so
   the "View archived snapshot" link works from regions where covers.com is
   geo-restricted.
6. Writes `output/bonuses.json`.

## Data

`output/bonuses.json` — 3 records, one per casino. Fields:

| Field | Type | Notes |
|-------|------|-------|
| `casino` | string | Casino name |
| `welcome_bonus` | string \| null | As published on the source page |
| `wagering_requirement` | int \| null | Multiplier (e.g. `3` for 3x) |
| `minimum_deposit` | string \| null | As published |
| `source_url` | string | The page the data was pulled from |
| `archive_url` | string \| null | Wayback Machine snapshot of the source |

**Nulls are intentional.** Covers.com does not publish every field for every
casino. We report `null` rather than invent a value.

## Why the source link opens an archived page

covers.com geo-blocks direct browser visits from some regions (a request from
South Africa returns a CloudFront 403). The scraper itself is unaffected — it
uses a plain HTTPS request with a browser-like User-Agent, which covers.com
serves normally. To make the "View archived snapshot" link useful for any
reviewer, the scraper stores a Wayback Machine snapshot URL alongside the
original source URL.

## Setup

Requires Python 3.12+.

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt