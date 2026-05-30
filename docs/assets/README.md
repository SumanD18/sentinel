# Demo asset

The README links to `docs/assets/demo.gif` (currently commented out so there's no
broken image). To add the demo:

1. Start the stack and seed demo data:
   ```bash
   docker compose up --build
   pip install -e packages/sdk-python
   python examples/quickstart/seed_demo.py
   ```
2. Open <http://localhost:3000> and record a ~10-15 second screen capture that
   shows:
   - the **Overview** (cost/latency cards + charts),
   - a **trace** opened to the waterfall with a span selected, and
   - the **Alerts** feed with the flagged hallucination.
3. Export as a GIF (recommended ~840px wide, < 5 MB so it loads fast). Tools:
   [Kap](https://getkap.co/), [LICEcap](https://www.cockos.com/licecap/), or
   `ffmpeg` from a screen recording.
4. Save it here as `demo.gif`.
5. In the root `README.md`, uncomment the `<img src="docs/assets/demo.gif">` line
   in the **Demo** section.

A good demo GIF is the single highest-leverage thing for converting repo visitors
into stargazers, so it's worth getting a clean take.
