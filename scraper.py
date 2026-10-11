from dotenv import load_dotenv
load_dotenv()

import json
import os
import re
import ssl
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from google import genai
from pydantic import BaseModel, Field, ValidationError
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

SOURCE_URL = "https://www.covers.com/casino/sweepstakes"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
TARGET_CASINOS = ["Crown Coins", "LoneStar Casino", "Stake.us"]
OUTPUT_PATH = Path("output/bonuses.json")
DEBUG = os.environ.get("SCRAPER_DEBUG") == "1"


class CasinoBonus(BaseModel):
    casino: str
    welcome_bonus: str | None = None
    wagering_requirement: int | None = Field(
        None, description="Wagering multiplier, e.g. 35 for 35x"
    )
    minimum_deposit: str | None = None
    source_url: str
    archive_url: str | None = None


class BrowserTLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        ctx.options |= 0x4
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def make_session() -> requests.Session:
    s = requests.Session()
    s.mount("https://", BrowserTLSAdapter())
    s.headers.update(
        {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return s


def fetch_page(session: requests.Session) -> str:
    r = session.get(SOURCE_URL, timeout=30)
    r.raise_for_status()
    return r.text


def get_archive_url(session: requests.Session, original_url: str) -> str:
    """Return a Wayback Machine URL that always resolves to a snapshot."""
    # 1) Try the availability API for a pinned snapshot
    try:
        r = session.get(
            "https://archive.org/wayback/available",
            params={"url": original_url},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        closest = data.get("archived_snapshots", {}).get("closest", {})
        if closest.get("available") and closest.get("url"):
            pinned = closest["url"].replace("http://", "https://", 1)
            print(f"  found pinned snapshot: {pinned}")
            return pinned
    except Exception as e:
        print(f"  WARN: Wayback API failed: {e}")

    # 2) Fallback: /web/2/<URL> always redirects to the nearest snapshot
    fallback = f"https://web.archive.org/web/2/{original_url}"
    print(f"  using fallback: {fallback}")
    return fallback


def _clean_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "svg", "nav", "header", "footer"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)


def extract_casino_block(html: str, casino: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "header", "footer"]):
        tag.decompose()

    variants = []
    for v in [casino, casino.replace(" Casino", "").strip(), casino.split()[0]]:
        if v and v not in variants:
            variants.append(v)

    heading = None
    for h in soup.find_all(["h2", "h3", "h4"]):
        ht = h.get_text(" ", strip=True).lower()
        if any(v.lower() in ht for v in variants):
            heading = h
            break

    if heading is not None:
        parts = [heading.get_text(" ", strip=True)]
        total = len(parts[0])
        for sib in heading.find_all_next():
            if sib.name in ("h2", "h3") and sib is not heading and len(parts) > 1:
                break
            txt = sib.get_text(" ", strip=True) if hasattr(sib, "get_text") else ""
            if txt and txt not in parts[-1]:
                parts.append(txt)
                total += len(txt)
            if total > 4000:
                break
        block = " ".join(parts)
        if len(block) > 200:
            return block[:4000]

    text = _clean_text(BeautifulSoup(html, "html.parser"))
    for v in variants:
        idx = text.lower().find(v.lower())
        if idx != -1:
            return text[max(0, idx - 200): idx + 3500]
    return None


PROMPT = """You extract structured casino bonus data from a block of text.

Return ONLY a JSON object with exactly these fields:
- welcome_bonus: string describing the welcome/no-purchase bonus, or null
- wagering_requirement: integer multiplier (e.g. 35 for 35x), or null if not stated
- minimum_deposit: string describing minimum deposit/purchase, or null if not stated

Do not invent values. If a field is not clearly stated in the text, use null.
Return valid JSON only, with no surrounding prose or markdown fences.

Casino: {casino}

Text:
{text}
"""


def llm_extract(client: genai.Client, casino: str, block: str, attempts: int = 4) -> dict:
    prompt = PROMPT.format(casino=casino, text=block)
    last_err = None
    for i in range(attempts):
        try:
            response = client.models.generate_content(
                model="gemini-flash-latest",
                contents=prompt,
            )
            raw = response.text.strip()
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
            if not raw.startswith("{"):
                m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
                if m:
                    raw = m.group(0)
            return json.loads(raw)
        except Exception as e:
            last_err = e
            wait = 4 * (i + 1)
            print(f"  attempt {i+1}/{attempts} failed ({type(e).__name__}: {e}). Retrying in {wait}s...")
            time.sleep(wait)
    raise last_err


def main() -> int:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY is not set.")
        return 1

    client = genai.Client(api_key=api_key)
    session = make_session()

    print(f"Fetching {SOURCE_URL} ...")
    html = fetch_page(session)
    print(f"  got {len(html):,} chars of HTML")

    print("Looking up Wayback Machine snapshot...")
    archive_url = get_archive_url(session, SOURCE_URL)
    print(f"  archive: {archive_url}")

    results = []
    for casino in TARGET_CASINOS:
        print(f"\n--- {casino} ---")
        block = extract_casino_block(html, casino)
        if not block:
            print(f"  WARN: could not find '{casino}' in page text. Skipping.")
            continue

        print(f"  extracted {len(block)} chars of context")
        if DEBUG:
            print(f"  PREVIEW: {block[:500]!r}")

        try:
            data = llm_extract(client, casino, block)
        except json.JSONDecodeError as e:
            print(f"  ERROR: LLM did not return valid JSON: {e}")
            continue
        except Exception as e:
            print(f"  ERROR calling LLM after retries: {e}")
            continue

        data["casino"] = casino
        data["source_url"] = SOURCE_URL
        data["archive_url"] = archive_url

        try:
            validated = CasinoBonus(**data)
        except ValidationError as e:
            print(f"  WARN: validation failed: {e}")
            continue

        print(f"  OK: {validated.model_dump()}")
        results.append(validated.model_dump())

        time.sleep(2)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {len(results)} records to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())