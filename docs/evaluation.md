# ScamSense Evaluation Strategy

## Test layers

| Layer | Location | What it covers |
|---|---|---|
| Unit | `tests/unit/*.py` | deterministic analyzers (URL, phone, email headers, QR) and the extract -> RAG -> LLM pipeline in both LLM-online and LLM-offline modes |
| Integration | `tests/unit/test_api.py`, `test_analyze.py` | endpoint contracts, persistence, ownership scoping, upload validation |
| End-to-end | `apps/web/tests/e2e/full_flow.js` | Playwright run through the real UI: register -> text check -> report -> screenshot upload -> history scoping -> email headers -> QR code -> assistant follow-up |

## Running the suites

```bash
# Unit + integration (73 tests)
python -m pytest tests -q

# E2E: requires backend on :8000, npm start on :3000, and Ollama running
cd apps/web && node tests/e2e/full_flow.js
```

E2E fixtures live in `%LOCALAPPDATA%\Temp` and are generated once (see the header comment in `full_flow.js` for the two one-liners).

## Current baseline
- 73/73 unit tests passing (7 of them cover the assistant).
- 9/9 E2E steps passing with a live local Ollama (`phi3:mini`).
- `next build` compiles clean.

## Not yet measured
- Precision / recall / F1 and false-positive rates for the detectors.
- Latency and cost per analysis.
- Calibration of the heuristic index against labelled real-world scam corpora.

Scores are heuristic indices, not calibrated probabilities. Any future detector must add labelled fixtures and report its false-positive rate before shipping.