import sys
import ssl
import urllib.robotparser as rp
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from bs4 import BeautifulSoup

BASE = "https://www.covers.com"
PATH = "/casino/sweepstakes"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


class BrowserTLSAdapter(HTTPAdapter):
    """Force a browser-like TLS context so CloudFront accepts the handshake."""

    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        # OP_LEGACY_SERVER_CONNECT — some CDNs still expect this
        ctx.options |= 0x4
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def make_session():
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


def check_robots(session):
    url = BASE + "/robots.txt"
    r = session.get(url, timeout=30)
    print(f"robots.txt status: {r.status_code}")
    if r.status_code == 200:
        print("---- robots.txt (first 1500 chars) ----")
        print(r.text[:1500])
        print("---------------------------------------")
        parser = rp.RobotFileParser()
        parser.parse(r.text.splitlines())
        allowed = parser.can_fetch(UA, BASE + PATH)
        print(f"Path {PATH} allowed for our UA: {allowed}")
        return allowed
    elif r.status_code == 404:
        print("No robots.txt -> default allow")
        return True
    else:
        print(f"Unexpected status {r.status_code} -> treat as disallow")
        return False


def main():
    session = make_session()

    print("=== STEP 1: robots.txt ===")
    if not check_robots(session):
        print("STOP: robots.txt disallows us. Pick another source.")
        sys.exit(1)

    print("\n=== STEP 2: Fetch the target page ===")
    r = session.get(BASE + PATH, timeout=30)
    print(f"HTTP status: {r.status_code}")
    print(f"Content-Type: {r.headers.get('content-type')}")
    print(f"Body length: {len(r.text)} chars")

    body_lower = r.text.lower()
    cf = any(s in body_lower for s in ["just a moment", "checking your browser"])
    print(f"Cloudflare interstitial detected: {cf}")

    print("\n=== STEP 3: Do the fields we need exist on the page? ===")
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text(" ", strip=True)
    text_lower = text.lower()

    checks = {
        "bonus": "bonus" in text_lower,
        "wagering": "wagering" in text_lower,
        "playthrough": "playthrough" in text_lower or "play through" in text_lower,
        "deposit": "deposit" in text_lower,
        "sweepstakes": "sweepstakes" in text_lower,
        "promo": "promo" in text_lower,
    }
    for k, v in checks.items():
        print(f"  '{k}' found: {v}")

    print("\n=== STEP 4: First 2000 chars of visible text ===")
    print(text[:2000])

    print("\n=== STEP 5: Does the page list multiple casinos? ===")
    brand_hits = []
    for brand in [
        "Crown", "LoneStar", "Lone Star", "Stake", "McLuck", "Pulsz",
        "MegaBonanza", "Mega Bonanza", "WOW Vegas", "Hello Millions",
        "Real Prize", "SplashCoins", "Sweeps Royal", "MyPrize",
    ]:
        if brand.lower() in text_lower:
            brand_hits.append(brand)
    print(f"  Casinos mentioned: {brand_hits}")

    print("\n=== VERDICT ===")
    passed = (
        r.status_code == 200
        and not cf
        and checks["bonus"]
        and len(brand_hits) >= 3
    )
    if passed:
        print("PASS - page is scrapeable and lists multiple casinos.")
        print(f"       Found {len(brand_hits)} brands: {brand_hits}")
    else:
        print("FAIL - do not scrape. Reason(s):")
        if r.status_code != 200:
            print(f"  - HTTP status was {r.status_code}")
        if cf:
            print("  - Cloudflare interstitial detected")
        if not checks["bonus"]:
            print("  - No 'bonus' text found in page")
        if len(brand_hits) < 3:
            print(f"  - Only {len(brand_hits)} casinos found (need 3+): {brand_hits}")


if __name__ == "__main__":
    main()