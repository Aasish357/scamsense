# Evaluation corpus

A small, labelled corpus of scam and benign messages, emails and QR payloads used
by `scripts/evaluate.py` to measure the detectors.

## Format

JSONL, one sample per line:

```json
{
  "id": "txt-scam-001",
  "modality": "text | email | qr",
  "label": "scam | benign",
  "content": "the message / raw email / QR payload",
  "expect": ["url.suspicious_tld", "url.brand_foreign_domain"],
  "notes": "why this sample is in the corpus"
}
```

- **`expect` on a scam sample** lists the detectors a security analyst would say
  *must* fire. Recall is measured against this list.
- **`expect` on a benign sample** lists signals that may legitimately fire (a
  real `.zip` attachment, a forwarded message with a stripped header chain).
  Any *other* signal on a benign sample counts as a false alarm.
- Extra signals on a scam sample are reported as `extras` rather than penalised:
  the corpus records what each sample was designed to trigger, so a surprising
  extra is a finding for a human to review.

QR samples store the **payload string**; the harness encodes it into an image and
runs the real OpenCV decode, so no binary fixtures are committed.

## Safety rules

- **No live hosts.** Every host is under a reserved, unroutable domain
  (`.example`, `.test`, `.invalid`) or a documentation domain, except `bit.ly`
  and `wa.me` at invented slugs, which the shortener detector needs.
  `tests/unit/test_evaluation.py` enforces this.
- Because of that, the **suspicious-TLD** rule is covered by a unit test rather
  than a corpus sample: committing a registrable `.top`/`.xyz` host would put a
  clickable phishing-shaped link in a public repository.
- Nothing in the corpus is scraped, purchased or copied from a real dataset.

## Adding samples

1. Write the sample with the *designed* expectation, never with whatever the
   engine currently outputs - otherwise the harness only measures how well the
   engine agrees with itself.
2. Keep benign controls that are genuinely tricky (`apply-now.example.com`,
   sequential order ids, deep but real subdomains) - they are what catches an
   over-eager detector.
3. Run `python scripts/evaluate.py`. If a number moves for a good reason, review
   it and then `python scripts/evaluate.py --update-baseline`.

## Scaling it up (free)

Drop any CSV/TSV/JSONL dataset you already have into `corpus/external/`
(gitignored) and run `python scripts/evaluate.py --external`. The importer looks
for a label column (`label`, `class`, `is_phishing`, `target`) and a content
column (`text`, `content`, `message`, `url`, `body`). External samples have no
per-detector expectations, so they are measured end to end only.

No API keys, no network access, no paid services.