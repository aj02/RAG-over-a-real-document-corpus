# Eval results

Each run lands in this directory as a pair of files:

- `run_<UTC-stamp>.md` — human-readable report with per-question detail
  and aggregate metrics
- `run_<UTC-stamp>.json` — machine-readable sidecar for diffing across runs

To produce the first run:

```bash
docker compose up -d --build
python scripts/download_corpus.py
python -m scripts.ingest_cli
python -m eval.run_eval --base-url http://localhost:8000
```

After the run, paste the aggregate table from the latest markdown report
into the top-level `README.md` under "Eval results" so visitors see real
numbers, not just claims.
