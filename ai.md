# AI reflection

**1. Tool used**

Claude (Anthropic web interface) for the scraper, the Nuxt page, and this
write-up. Google Gemini `gemini-flash-latest` as the LLM inside the scraper
that turns free-text bonus terms into the three structured fields
(welcome_bonus, wagering_requirement, minimum_deposit).

**2. Where the AI was wrong #1 — deprecated SDK**

The AI recommended the `google.generativeai` Python package for calling
Gemini. On first run, Python printed a `FutureWarning` saying the package
was deprecated and pointing at a migration guide
(`github.com/google-gemini/deprecated-generative-ai-python`). The package
stopped receiving updates on 30 November 2025.

**How I caught it:** I read the terminal output instead of assuming the code
worked. A `FutureWarning` that names a deprecation date is a strong signal —
I switched to the current `google-genai` package, which uses
`from google import genai` and `client.models.generate_content(...)`.

**3. Where the AI was wrong #2 — wrong text block**

The first version of `extract_casino_block()` grabbed the first 3,000
characters of page text after the casino's name. On covers.com, the first
occurrence of each casino name is in the top navigation menu, not the review
block. The LLM was fed page chrome, so it returned `null` for
`wagering_requirement` and `minimum_deposit` on every casino.

**How I caught it:** I ran the script, saw the nulls, and printed a preview
of the text block that was being sent to Gemini. The preview was clearly
navigation links, not review text. Fix: search for the casino name inside
H2/H3/H4 headings first, then extract text until the next heading. That
targets the actual review section.

**4. Where the AI was wrong #3 — no retry logic**

The first version of `llm_extract()` had no error handling. Gemini returned
a `503 UNAVAILABLE` ("This model is currently experiencing high demand") on
the third casino, and the run dropped that record silently.

**How I caught it:** the third row was missing from `output/bonuses.json`.
Fix: wrapped the API call in a small exponential-backoff retry loop
(4 attempts, waits of 4s / 8s / 12s / 16s), and made the Pydantic model
accept `None` for `welcome_bonus` so a legitimate `null` from the model
doesn't crash validation.

**5. Where the AI was wrong #4 — TLS handshake**

The AI recommended `requests` with the default TLS context. CloudFront
(covers.com's CDN) rejected that handshake with a silent timeout — the same
URL worked fine with `curl.exe` on the same machine, so it wasn't a network
problem. The default Python TLS cipher list and extension order don't match
what CloudFront expects.

**How I caught it:** compared the Python failure against a `curl.exe` success
against the same URL, which narrowed the cause to the TLS fingerprint rather
than the network. Fix: a `BrowserTLSAdapter` that sets
`ctx.minimum_version = TLSv1_2`, `DEFAULT@SECLEVEL=1` ciphers, and
`OP_LEGACY_SERVER_CONNECT`.

**Time taken**

Approximately 2 hours 45 minutes of focused work:

- ~30 min: source verification (next.io blocked → switched to covers.com),
  robots.txt checks, HTTP status checks
- ~60 min: writing and debugging the scraper (3 rounds of AI errors above)
- ~40 min: Nuxt 4 front end + separate CSS file + mobile-first layout
- ~15 min: Vercel deploy
- ~20 min: README, production.md, this file