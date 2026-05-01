# Capturing the README screenshots

The four PNGs referenced from the root `README.md` are produced by the
script in [`scripts/capture_screenshots.mjs`](../scripts/capture_screenshots.mjs).
It launches a headless Chromium via Playwright, drives the running web UI,
waits for the page to settle, and writes each screenshot into
`docs/screenshots/`.

## Prerequisites

- The full stack is running (`docker compose up -d --build`).
- The corpus has been downloaded and ingested:

  ```bash
  python scripts/download_corpus.py
  python -m scripts.ingest_cli
  ```

  Without ingestion, the API returns "no relevant context" and the answer
  screenshot is uninteresting.

## Run the capture

```bash
cd web
pnpm dlx -p playwright@1 -p @playwright/test playwright install --with-deps chromium
node ../scripts/capture_screenshots.mjs
```

The script writes:

| file                                  | route   | viewport          |
| ------------------------------------- | ------- | ----------------- |
| `docs/screenshots/ask-empty.png`      | `/`     | 1280 × 900        |
| `docs/screenshots/ask-answer.png`     | `/`     | 1280 × 1400       |
| `docs/screenshots/search.png`         | `/search` | 1280 × 1100     |
| `docs/screenshots/about.png`          | `/about` | 1280 × 1500      |

After capture, the README image links resolve and the table renders.

## Re-capturing in dark mode

```bash
SCREENSHOT_THEME=dark node ../scripts/capture_screenshots.mjs
```

Dark variants land alongside the light ones with a `-dark` suffix; the
README does not currently link to those, but you can swap them in if you
prefer that aesthetic for the headline.
