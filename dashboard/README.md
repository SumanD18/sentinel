# sentinel-dashboard

React + TypeScript dashboard for Sentinel: trace waterfalls, cost/latency
overview, the alert feed, and the prompt registry.

## Develop

```bash
npm install
npm run dev        # http://localhost:5173 (proxies /api, /v1, /metrics to :8000)
```

Run the collector alongside it: `sentinel-server --reload` (or
`docker compose up server`).

## Build

```bash
npm run build      # type-checks then emits static assets to dist/
npm run preview    # serve the production build locally
```

## Configuration

| Env var | Purpose |
| --- | --- |
| `VITE_API_BASE` | API origin (empty = same origin / dev proxy) |
| `VITE_API_KEY` | bearer token when the server has auth enabled |

In production the dashboard is served by nginx (see [`Dockerfile`](Dockerfile) and
[`nginx.conf`](nginx.conf)), which reverse-proxies the API so the browser sees a
single origin.
