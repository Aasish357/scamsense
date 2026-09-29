# ScamSense Evaluation Strategy

## What is measured

`scripts/evaluate.py` runs the deterministic detectors over a labelled corpus
and reports, per detector, precision / recall / F1, plus end-to-end detection
rate, false-alarm rate, score separation and latency. It is offline, free and
deterministic: no LLM, no network, no paid services.

```bash
python scripts/evaluate.py                     # full report
python scripts/evaluate.py --quiet             # one-line summary
python scripts/evaluate.py --update-baseline   # accept the current numbers
python scripts/evaluate.py --report            # write docs/evaluation-report.md
python scripts/evaluate.py --external          # add datasets from corpus/external/
```

## The corpus

90 labelled samples in `corpus/dataset.jsonl` (40 scam / 50 benign) across text,
raw email and QR payloads, documented in `corpus/README.md`. Two properties are
enforced by tests:

- **No live hosts.** Every host sits under a reserved, unroutable domain
  (`.example`, `.test`, `.invalid`), except `bit.ly` and `wa.me` at invented
  slugs, which the shortener detector needs. Committing a registrable `.top`
  host would put a clickable phishing-shaped link in a public repo, so the
  suspicious-TLD rule is covered by a unit test instead of a corpus sample.
- **Expectations are written from design intent**, never from the engine's
  current output, so the harness cannot flatter the engine.

## Current results

| Metric | Value |
|---|---|
| Scam detection rate | 100% (40/40) |
| False-alarm rate on benign (strong signal) | 0% (0/50) |
| Benign samples scoring >= 50 | 0% |
| Mean risk index, scam / benign | 78.5 / 2.3 |
| Latency p95 | ~22 ms (QR includes an OpenCV encode+decode round trip) |

Per-detector numbers: `docs/evaluation-report.md`.

## What the harness found (and fixed)

The first run was the point of building it:

1. **The base heuristic was the biggest false-positive source.** The MVP
   placeholder scored any message over 100 characters at 50, and *any* URL at
   70 - so 41% of benign samples scored "suspicious" or worse, including
   "Your order has shipped. Track it at https://www.example.com/orders/987654".
   Scoring is now detector-driven: the index reflects only what a detector
   found. Benign mean score fell 25.7 -> 2.3 and the score false-positive rate
   41% -> 0%, with detection unchanged.
2. **A UPI/crypto payment request in plain SMS was invisible.** `upi://pay?...`
   is neither a URL nor a dialable number, so every detector missed it. Added
   `text_signals.py`.
3. **`paypa1.com` was classified as a typosquat, not a digit-swap**, because the
   leet map maps `1 -> i` and cannot express `1 -> l`. Added a second
   substitution map.
4. **UK 090x premium numbers were not detected**; `/reset` and `/recover` were
   not treated as credential-themed paths.
5. **A credential-themed path alone pushed a first-party `/reset` link to 50**,
   and a business-card QR (`tel:`/`mailto:`) inherited the QR base score. Both
   are now informational.
6. **The corpus contained live suspicious TLDs** - caught by the corpus safety
   test and rewritten onto reserved domains.

## Gates

- `tests/unit/test_evaluation.py` fails the build if a corpus sample produces a
  signal with no registered code, if the corpus references a live host, if a
  benign sample scores >= 50, or if any metric regresses against
  `corpus/baseline.json`.
- `.github/workflows/evaluation.yml` runs the suite plus the harness on every
  push. Latency is reported but deliberately **not** gated: it swings by an
  order of magnitude with machine load, so a loose absolute ceiling is used
  instead.

## Honest limitations

- The corpus is synthetic and self-authored. 100% detection means "the detectors
  catch what they were built to catch", not "ScamSense catches real scams".
  Real adversarial text (obfuscation, code-switching, novel lures) is not
  represented at all.
- The LLM path is not evaluated: the harness measures the deterministic engine
  only, so a prompt change cannot move these numbers.
- Per-detector precision/recall on sparse codes rests on 1-5 samples each. The
  table is a regression guard, not a confidence interval.
- Still unmeasured: recall against live phishing corpora, adversarial robustness,
  latency percentiles under real load, and any cost model.

## Next

Grow the corpus with real-world samples (via `corpus/external/`, free and
local), add adversarial/obfuscated variants, and measure the LLM path's
contribution separately from the deterministic engine.