"""ScamSense evaluation harness.

Runs the deterministic detectors over a labelled corpus and reports, per
detector, precision / recall / F1 plus the end-to-end false-alarm rate, score
separation and latency. It is offline, free and deterministic: no LLM, no
network, no paid services.

    python scripts/evaluate.py                     # human-readable report
    python scripts/evaluate.py --update-baseline   # commit the current numbers
    python scripts/evaluate.py --report            # also write docs/evaluation-report.md

Corpus format: JSONL, one sample per line (see corpus/README.md).
External datasets: drop CSV/TSV/JSONL files into corpus/external/ (gitignored)
and they are picked up automatically - useful for the free public corpora you
download yourself. No API keys, no network access.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import statistics
import sys
import time
from typing import Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):  # the corpus contains non-Latin samples
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from apps.web.src.app.api import signal_codes  # noqa: E402
from apps.web.src.app.api.check import assess_content_heuristically  # noqa: E402
from apps.web.src.app.api.email_analysis import analyze_email  # noqa: E402
from apps.web.src.app.api.qr_analysis import analyze_qr  # noqa: E402

DEFAULT_DATASET = os.path.join(ROOT, "corpus", "dataset.jsonl")
EXTERNAL_DIR = os.path.join(ROOT, "corpus", "external")
BASELINE_PATH = os.path.join(ROOT, "corpus", "baseline.json")

# Codes that are contextual rather than fraud-indicating. They are still
# measured, but a sample firing one of these is not counted as a false alarm
# unless the sample did not expect it - "not HTTPS" on its own proves nothing.
WEAK_CODES = {
    "url.no_https",
    "url.multiple_hyphens",
    "url.long_url",
    "url.long_hostname",
    "url.credential_path",
    "url.many_subdomains",
    "email.no_auth_results",
    "email.missing_message_id",
    "email.no_received_chain",
    "email.html_only",
    "email.archive_attachment",
    "qr.link_benign",
    "qr.plain_text",
    "qr.mailto",
    "qr.tel",
    "text.tel_uri",
}

SCAM_BAND_MIN = 50  # score at or above this counts as "flagged" end to end


def _decode_row(raw: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "ignore")


def load_dataset(path: str) -> List[Dict]:
    samples: List[Dict] = []
    with io.open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                sample = json.loads(line)
            except ValueError as error:
                raise SystemExit("{}:{} is not valid JSON ({})".format(path, line_number, error))
            for field in ("id", "modality", "label", "content"):
                if field not in sample:
                    raise SystemExit(
                        "{}:{} is missing the required field '{}'".format(path, line_number, field)
                    )
            if sample["label"] not in ("scam", "benign"):
                raise SystemExit("{}:{} has an unknown label".format(path, line_number))
            sample.setdefault("expect", [])
            sample.setdefault("notes", "")
            sample.setdefault("source", os.path.basename(path))
            samples.append(sample)
    return samples


def load_external(directory: str) -> List[Dict]:
    """Load any free datasets the user dropped in corpus/external/.

    Accepts .jsonl (same schema as the curated corpus) and .csv/.tsv with a
    label column plus one of url/text/content/message.
    """
    samples: List[Dict] = []
    if not os.path.isdir(directory):
        return samples
    label_keys = ("label", "class", "is_phishing", "target")
    content_keys = ("content", "text", "message", "url", "body", "letter")
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        if not os.path.isfile(path):
            continue
        if name.endswith((".jsonl", ".ndjson")):
            samples.extend(load_dataset(path))
        elif name.endswith((".csv", ".tsv")):
            delimiter = "\t" if name.endswith(".tsv") else ","
            with io.open(path, encoding="utf-8", errors="replace", newline="") as handle:
                for index, row in enumerate(csv.DictReader(handle, delimiter=delimiter)):
                    label = next((str(row[k]).strip() for k in label_keys if k in row), "")
                    content = next((str(row[k]) for k in content_keys if k in row and row[k]), "")
                    if not content:
                        continue
                    samples.append(
                        {
                            "id": "{}-{}".format(name, index),
                            "modality": "text",
                            "label": "scam" if label.lower() in ("1", "phishing", "scam", "true") else "benign",
                            "content": content,
                            "expect": [],
                            "notes": "external dataset sample (no per-detector expectation)",
                            "source": name,
                        }
                    )
    return samples


def _qr_analysis_for(payload: str) -> Dict:
    """Prefer the real encode/decode round trip when OpenCV is available."""
    try:
        import cv2
    except ImportError:
        from apps.web.src.app.api.qr_analysis import analyze_qr as _fallback

        return _fallback(None)  # no image: harness falls back to the payload
    matrix = cv2.QRCodeEncoder_create().encode(payload)
    scaled = cv2.resize(matrix, None, fx=10, fy=10, interpolation=cv2.INTER_NEAREST)
    padded = cv2.copyMakeBorder(scaled, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)
    ok, buffer = cv2.imencode(".png", padded)
    if not ok:
        raise SystemExit("could not encode the QR sample '{}'".format(payload))
    return analyze_qr(buffer.tobytes())


def _structured_signals(text: str) -> List[str]:
    """Per-detector signal strings for a blob of text (URLs and phone numbers)."""
    from apps.web.src.app.api.extraction import extract_links
    from apps.web.src.app.api.phone_analysis import analyze_phones
    from apps.web.src.app.api.text_signals import analyze_text_signals
    from apps.web.src.app.api.url_analysis import analyze_urls

    signals: List[str] = []
    for result in analyze_urls(extract_links(text))["results"]:
        signals.extend(result["signals"])
    for result in analyze_phones(text)["results"]:
        signals.extend(result["signals"])
    signals.extend(analyze_text_signals(text)["signals"])
    return signals


def observe(sample: Dict, qr_roundtrip: bool = True) -> Dict:
    """Run the deterministic pipeline for one sample and collect signal codes."""
    started = time.perf_counter()
    content = sample["content"]
    modality = sample["modality"]
    unmapped: List[str] = []

    # Codes come from the analyzers' own per-item signal lists. The evidence
    # strings that check.py joins for display are narrative and are not parsed.
    if modality == "email":
        result = analyze_email(content)
        body = result["parsed"]["body"] or content
        heuristic = assess_content_heuristically(body)
        evidence = list(result["signals"]) + _structured_signals(body)
        score = max(heuristic["risk_score"], result["suggested_score"])
    elif modality == "qr":
        if qr_roundtrip:
            result = _qr_analysis_for(content)
        else:
            result = {"content": content, "signals": [], "suggested_score": 0, "payloads": [content]}
        heuristic = assess_content_heuristically(result["content"])
        evidence = list(result["signals"]) + _structured_signals(result["content"])
        score = max(heuristic["risk_score"], result["suggested_score"])
    else:
        heuristic = assess_content_heuristically(content)
        evidence = _structured_signals(content)
        score = heuristic["risk_score"]

    mapped = signal_codes.codes_for_signals(evidence)
    unmapped = mapped["unmapped"]
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return {
        "id": sample["id"],
        "codes": mapped["codes"],
        "unmapped": unmapped,
        "score": score,
        "latency_ms": elapsed_ms,
    }

def _entry(code: str) -> Dict[str, int]:
    return {"tp": 0, "fp": 0, "fn": 0, "tolerated": 0, "extras": 0}


def _ratio(numerator: float, denominator: float) -> Optional[float]:
    return numerator / denominator if denominator else None


def _f1(precision: Optional[float], recall: Optional[float]) -> Optional[float]:
    if precision is None or recall is None or (precision + recall) == 0:
        return None
    return 2 * precision * recall / (precision + recall)


def compute_metrics(samples: List[Dict], observations: List[Dict]) -> Dict:
    per_code: Dict[str, Dict[str, int]] = {}

    for sample, observation in zip(samples, observations):
        expected = set(sample.get("expect") or [])
        fired = set(observation["codes"])
        is_scam = sample["label"] == "scam"
        for code in fired:
            entry = per_code.setdefault(code, _entry(code))
            if is_scam:
                if code in expected:
                    entry["tp"] += 1
                else:
                    entry["extras"] += 1
            else:
                if code in expected:
                    entry["tolerated"] += 1
                else:
                    entry["fp"] += 1
        if is_scam:
            for code in expected - fired:
                per_code.setdefault(code, _entry(code))["fn"] += 1

    detector_rows = []
    for code in sorted(per_code):
        counts = per_code[code]
        precision = _ratio(counts["tp"], counts["tp"] + counts["fp"])
        recall = _ratio(counts["tp"], counts["tp"] + counts["fn"])
        detector_rows.append(
            {
                "code": code,
                "family": signal_codes.family_of(code),
                "tp": counts["tp"],
                "fp": counts["fp"],
                "fn": counts["fn"],
                "tolerated": counts["tolerated"],
                "extras": counts["extras"],
                "precision": precision,
                "recall": recall,
                "f1": _f1(precision, recall),
            }
        )

    scam_samples = [s for s in samples if s["label"] == "scam"]
    benign_samples = [s for s in samples if s["label"] == "benign"]

    detected = 0
    for sample, observation in zip(samples, observations):
        if sample["label"] != "scam":
            continue
        expected = set(sample.get("expect") or [])
        fired = set(observation["codes"])
        if expected:
            if expected & fired:
                detected += 1
        elif observation["score"] >= SCAM_BAND_MIN:
            detected += 1

    false_alarms = 0
    any_signal_benign = 0
    scored_benign = 0
    for sample, observation in zip(samples, observations):
        if sample["label"] != "benign":
            continue
        expected = set(sample.get("expect") or [])
        unexpected = {
            code
            for code in observation["codes"]
            if code not in expected and code not in WEAK_CODES
        }
        if unexpected:
            false_alarms += 1
        if observation["codes"]:
            any_signal_benign += 1
        if observation["score"] >= SCAM_BAND_MIN:
            scored_benign += 1

    scam_scores = [o["score"] for s, o in zip(samples, observations) if s["label"] == "scam"]
    benign_scores = [o["score"] for s, o in zip(samples, observations) if s["label"] == "benign"]
    latencies = sorted(o["latency_ms"] for o in observations)

    def percentile(values: List[float], fraction: float) -> Optional[float]:
        if not values:
            return None
        index = min(len(values) - 1, int(round(fraction * (len(values) - 1))))
        return values[index]

    by_modality: Dict[str, float] = {}
    for modality in sorted({s["modality"] for s in samples}):
        values = [o["latency_ms"] for s, o in zip(samples, observations) if s["modality"] == modality]
        by_modality[modality] = round(statistics.median(values), 2) if values else 0.0

    return {
        "samples": len(samples),
        "scam_samples": len(scam_samples),
        "benign_samples": len(benign_samples),
        "detection_rate": _ratio(detected, len(scam_samples)),
        "false_alarm_rate": _ratio(false_alarms, len(benign_samples)),
        "any_signal_rate_on_benign": _ratio(any_signal_benign, len(benign_samples)),
        "score_false_positive_rate": _ratio(scored_benign, len(benign_samples)),
        "scam_mean_score": round(statistics.mean(scam_scores), 1) if scam_scores else 0.0,
        "benign_mean_score": round(statistics.mean(benign_scores), 1) if benign_scores else 0.0,
        "scam_median_score": round(statistics.median(scam_scores), 1) if scam_scores else 0.0,
        "benign_median_score": round(statistics.median(benign_scores), 1) if benign_scores else 0.0,
        "latency_mean_ms": round(statistics.mean(latencies), 2) if latencies else 0.0,
        "latency_p95_ms": round(percentile(latencies, 0.95) or 0.0, 2),
        "latency_median_by_modality_ms": by_modality,
        "detectors": detector_rows,
        "unmapped_signals": sorted(
            {signal for o in observations for signal in o["unmapped"]}
        ),
    }


# Reported on every run...
HEADLINE = (
    "detection_rate",
    "false_alarm_rate",
    "score_false_positive_rate",
    "scam_mean_score",
    "benign_mean_score",
    "latency_p95_ms",
)

# ...but only these gate the run. Latency swings by an order of magnitude with
# machine load and the QR encode/decode round trip, so gating on it would make
# the harness flaky rather than useful. tests/unit/test_evaluation.py keeps a
# loose absolute ceiling on it instead.


def _percent(value: Optional[float]) -> str:
    return "n/a" if value is None else "{:.0f}%".format(value * 100)


def format_report(metrics: Dict, samples: List[Dict], observations: List[Dict]) -> str:
    lines = []
    lines.append("ScamSense evaluation report")
    lines.append("=" * 72)
    lines.append(
        "corpus: {} samples ({} scam / {} benign)".format(
            metrics["samples"], metrics["scam_samples"], metrics["benign_samples"]
        )
    )
    lines.append("")
    lines.append("End to end")
    lines.append("-" * 72)
    lines.append("  scam detection rate (>=1 expected signal, else score >= {}) : {}".format(
        SCAM_BAND_MIN, _percent(metrics["detection_rate"])))
    lines.append("  false-alarm rate on benign (strong signal)                   : {}".format(
        _percent(metrics["false_alarm_rate"])))
    lines.append("  benign samples producing any signal                          : {}".format(
        _percent(metrics["any_signal_rate_on_benign"])))
    lines.append("  benign samples scoring >= {}                                   : {}".format(
        SCAM_BAND_MIN, _percent(metrics["score_false_positive_rate"])))
    lines.append("  mean risk index   scam {} / benign {} (median {} / {})".format(
        metrics["scam_mean_score"], metrics["benign_mean_score"],
        metrics["scam_median_score"], metrics["benign_median_score"]))
    lines.append("  latency per sample: mean {} ms, p95 {} ms".format(
        metrics["latency_mean_ms"], metrics["latency_p95_ms"]))
    for modality, value in sorted(metrics["latency_median_by_modality_ms"].items()):
        lines.append("    median {}: {} ms".format(modality, value))
    lines.append("")
    lines.append("Per detector (tp = expected and fired, fp = fired on benign and not expected,")
    lines.append("fn = expected but not fired, extras = additional true positives on scam samples)")
    lines.append("-" * 72)
    header = "{:<34} {:>4} {:>4} {:>4} {:>9} {:>7} {:>6}".format(
        "detector", "tp", "fp", "fn", "precision", "recall", "f1")
    lines.append(header)
    for row in sorted(metrics["detectors"], key=lambda r: (r["family"], r["code"])):
        lines.append(
            "{:<34} {:>4} {:>4} {:>4} {:>9} {:>7} {:>6}".format(
                row["code"],
                row["tp"],
                row["fp"],
                row["fn"],
                _percent(row["precision"]),
                _percent(row["recall"]),
                _percent(row["f1"]),
            )
        )
    lines.append("")
    if metrics["unmapped_signals"]:
        lines.append("UNMAPPED SIGNALS (register them in signal_codes.py):")
        for signal in metrics["unmapped_signals"]:
            lines.append("  - {}".format(signal))
    else:
        lines.append("All signals produced by the corpus are registered (no unmapped signals).")
    lines.append("")
    lines.append("Per-sample detail")
    lines.append("-" * 72)
    lines.append("{:<18} {:<7} {:>4}  {}".format("id", "label", "score", "signals"))
    for sample, observation in zip(samples, observations):
        codes = ", ".join(observation["codes"]) or "-"
        lines.append("{:<18} {:<7} {:>4}  {}".format(
            sample["id"], sample["label"], observation["score"], codes))
    return "\n".join(lines)


def compare_to_baseline(metrics: Dict, baseline: Dict) -> List[str]:
    """Return a list of human-readable regressions against the committed baseline."""
    regressions: List[str] = []
    for key in HEADLINE:
        if key == "latency_p95_ms":
            continue
        current = metrics.get(key)
        previous = baseline.get(key)
        if current is None or previous is None:
            continue
        if key == "detection_rate":
            if current < previous - 1e-9:
                regressions.append("{} dropped {} -> {}".format(key, previous, current))
        elif key in ("false_alarm_rate", "score_false_positive_rate"):
            if current > previous + 1e-9:
                regressions.append("{} rose {} -> {}".format(key, previous, current))
        elif key == "latency_p95_ms":
            if current > previous * 1.5 + 1.0:
                regressions.append("{} rose {} -> {}".format(key, previous, current))
        elif key == "scam_mean_score":
            if current < previous - 1e-9:
                regressions.append("{} dropped {} -> {}".format(key, previous, current))
        elif key == "benign_mean_score":
            if current > previous + 1e-9:
                regressions.append("{} rose {} -> {}".format(key, previous, current))

    previous_detectors = {row["code"]: row for row in baseline.get("detectors", [])}
    for row in metrics["detectors"]:
        previous = previous_detectors.get(row["code"])
        if not previous:
            continue
        if previous["recall"] is None or row["recall"] is None:
            continue
        if row["recall"] < previous["recall"] - 1e-9:
            regressions.append(
                "detector {} recall dropped {} -> {}".format(
                    row["code"], previous["recall"], row["recall"]
                )
            )
    return regressions


def write_report(path: str, metrics: Dict) -> None:
    lines = [
        "# Evaluation report",
        "",
        "Generated by `python scripts/evaluate.py --report` over the committed corpus.",
        "The corpus is deliberately synthetic (only domains we control appear in it), so",
        "these numbers measure the *detectors*, not the difficulty of real-world scams.",
        "",
        "## Headline",
        "",
        "| Metric | Value |",
        "|---|---|",
        "| Samples | {} ({} scam / {} benign) |".format(
            metrics["samples"], metrics["scam_samples"], metrics["benign_samples"]
        ),
        "| Scam detection rate | {} |".format(_percent(metrics["detection_rate"])),
        "| False-alarm rate on benign (strong signal) | {} |".format(
            _percent(metrics["false_alarm_rate"])),
        "| Benign samples scoring >= {} | {} |".format(
            SCAM_BAND_MIN, _percent(metrics["score_false_positive_rate"])),
        "| Mean score, scam / benign | {} / {} |".format(
            metrics["scam_mean_score"], metrics["benign_mean_score"]),
        "| Latency, mean / p95 | {} ms / {} ms |".format(
            metrics["latency_mean_ms"], metrics["latency_p95_ms"]),
        "",
        "## Per detector",
        "",
        "| detector | tp | fp | fn | tolerated | extras | precision | recall | f1 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in sorted(metrics["detectors"], key=lambda r: (r["family"], r["code"])):
        lines.append(
            "| `{}` | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                row["code"], row["tp"], row["fp"], row["fn"], row["tolerated"],
                row["extras"], _percent(row["precision"]), _percent(row["recall"]),
                _percent(row["f1"]),
            )
        )
    lines += [
        "",
        "`tolerated` = fired on a benign sample that expected it (a real .zip attachment,",
        "a forwarded message with a stripped header chain). `extras` = additional true",
        "positives on scam samples - reported for review rather than penalised, because the",
        "corpus only records the signals each sample was *designed* to trigger.",
        "",
    ]
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the ScamSense detectors.")
    parser.add_argument("--dataset", default=DEFAULT_DATASET, help="corpus JSONL path")
    parser.add_argument(
        "--external",
        action="store_true",
        help="also load free datasets dropped into corpus/external/",
    )
    parser.add_argument("--no-qr-roundtrip", action="store_true",
                        help="skip the OpenCV encode/decode round trip for QR samples")
    parser.add_argument("--update-baseline", action="store_true",
                        help="write corpus/baseline.json from this run")
    parser.add_argument("--report", action="store_true",
                        help="write docs/evaluation-report.md")
    parser.add_argument("--quiet", action="store_true", help="only print the summary")
    args = parser.parse_args()

    samples = load_dataset(args.dataset)
    if args.external:
        samples.extend(load_external(EXTERNAL_DIR))
    if not samples:
        print("no samples found in {}".format(args.dataset))
        return 2

    observations = [
        observe(sample, qr_roundtrip=not args.no_qr_roundtrip) for sample in samples
    ]
    metrics = compute_metrics(samples, observations)

    if not args.quiet:
        print(format_report(metrics, samples, observations))
        print("")
    print("detection {} | false alarms {} | score FPR {} | scam {} vs benign {} | p95 {} ms".format(
        _percent(metrics["detection_rate"]),
        _percent(metrics["false_alarm_rate"]),
        _percent(metrics["score_false_positive_rate"]),
        metrics["scam_mean_score"],
        metrics["benign_mean_score"],
        metrics["latency_p95_ms"],
    ))

    if args.report:
        write_report(os.path.join(ROOT, "docs", "evaluation-report.md"), metrics)
        print("wrote docs/evaluation-report.md")

    if metrics["unmapped_signals"]:
        print("")
        print("UNMAPPED SIGNALS - register them in signal_codes.py:")
        for signal in metrics["unmapped_signals"]:
            print("  - {}".format(signal))
        return 2

    if args.update_baseline:
        with io.open(BASELINE_PATH, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(metrics, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print("wrote corpus/baseline.json")
        return 0

    if os.path.exists(BASELINE_PATH):
        with io.open(BASELINE_PATH, encoding="utf-8") as handle:
            baseline = json.load(handle)
        regressions = compare_to_baseline(metrics, baseline)
        if regressions:
            print("")
            print("REGRESSIONS against corpus/baseline.json:")
            for item in regressions:
                print("  - {}".format(item))
            print("If the change is intended, re-run with --update-baseline.")
            return 1
        print("no regressions against corpus/baseline.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
