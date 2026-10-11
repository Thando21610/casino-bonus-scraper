import re
import ssl

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

ctx = create_urllib3_context()
ctx.minimum_version = ssl.TLSVersion.TLSv1_2
ctx.set_ciphers("DEFAULT@SECLEVEL=1")
ctx.options |= 0x4

adapter = HTTPAdapter()
orig_init = adapter.init_poolmanager

def patched_init(*args, **kwargs):
    kwargs["ssl_context"] = ctx
    return orig_init(*args, **kwargs)

adapter.init_poolmanager = patched_init

s = requests.Session()
s.mount("https://", adapter)
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
})

r = s.get("https://www.covers.com/casino/sweepstakes", timeout=30)
print(f"status: {r.status_code}, length: {len(r.text):,}")

links = re.findall(r'href="(/casino/[^"]+)"', r.text)
unique = []
for l in links:
    if l not in unique and "/casino/sweepstakes" not in l:
        unique.append(l)

print(f"\nFound {len(unique)} unique /casino/ links:\n")
for l in unique[:60]:
    print(l)