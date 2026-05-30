# Quickstart: seed demo traces

Populate a running Sentinel server with five realistic traces - no API keys, no
provider SDKs required. Great for kicking the tyres or for a demo.

```bash
# 1. Start the stack (repo root)
docker compose up --build

# 2. Install the SDK and seed
pip install -e packages/sdk-python
python examples/quickstart/seed_demo.py

# 3. Explore
open http://localhost:3000
```

You'll get:

- a **healthy** support-agent run (intent classification → answer),
- a **RAG** run with retrieval context,
- a **hallucination** (answer ignores its context → low trust score → alert),
- an **error** run (tool raises → critical alert),
- a **runaway loop** (55 LLM calls → critical alert).
