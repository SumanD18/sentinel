# Demo asset

`demo.gif` is the dashboard walkthrough embedded in the root README.

It is regenerated automatically on every GitHub release by
[`.github/workflows/demo-gif.yml`](../../.github/workflows/demo-gif.yml), which
boots the collector + dashboard with seeded demo data, drives the UI with
Playwright, encodes the frames to a GIF, and commits the refreshed result back
to `main`.

To regenerate it manually, trigger the workflow from the Actions tab
(`gh workflow run demo-gif.yml`) or run the capture locally; see
[`tools/demo-capture`](../../tools/demo-capture/README.md).
