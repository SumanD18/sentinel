# Demo GIF capture

Drives the live Sentinel dashboard with Playwright and encodes the README demo
GIF to `docs/assets/demo.gif`. Pure JavaScript (Playwright screenshots +
`gifenc`); no ffmpeg required.

This runs automatically on every GitHub release via
[`.github/workflows/demo-gif.yml`](../../.github/workflows/demo-gif.yml), which
commits the refreshed GIF back to `main`. You can also run it locally.

## Run locally

```bash
# 1. Start the collector with a throwaway DB
SENTINEL_DATABASE_URL="sqlite+aiosqlite:///./demo_gif.db" \
  python -m uvicorn sentinel_server.main:app --port 8000 --log-level warning &

# 2. Seed demo data (no API keys)
SENTINEL_ENDPOINT=http://localhost:8000 python examples/quickstart/seed_demo.py

# 3. Start the dashboard dev server (proxies /api to :8000)
( cd dashboard && npx vite --port 5173 --strictPort & )

# 4. Capture
cd tools/demo-capture
npm install
npx playwright install chromium
DASH_URL=http://localhost:5173 API_URL=http://localhost:8000 \
  OUT=../../docs/assets/demo.gif node capture.mjs
```

## Configuration (env vars)

| Var | Default | Purpose |
| --- | --- | --- |
| `DASH_URL` | `http://localhost:5173` | dashboard dev-server URL |
| `API_URL` | `http://localhost:8000` | collector URL (for seeding prompts) |
| `OUT` | `../../docs/assets/demo.gif` | output GIF path |

The capture walks Overview → Traces → a flagged-hallucination waterfall →
Alerts → Prompts and loops back, at 960x600.
