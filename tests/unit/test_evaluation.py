"""Tests for the evaluation harness and the detector-code registry.

The harness is the only thing standing between "we changed a detector" and
"nobody noticed the precision collapsed", so the corpus and the baseline are
tested like any other code.
"""
import importlib.util
import io
import json
import os

import pytest

from apps.web.src.app.api import signal_codes
from apps.web.src.app.main import app  # noqa: F401  (ensures the app imports)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORPUS = os.path.join(ROOT, "corpus", "dataset.jsonl")
BASELINE = os.path.join(ROOT, "corpus", "baseline.json")


def _load_harness():
    path = os.path.join(ROOT, "scripts", "evaluate.py")
    spec = importlib.util.spec_from_file_location("scamsense_evaluate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harness = _load_harness()


def _samples():
    return harness.load_dataset(CORPUS)


def test_corpus_exists_and_is_substantial():
    samples = _samples()
    assert len(samples) >= 60
    labels = {sample["label"] for sample in samples}
    assert labels == {"scam", "benign"}
    assert any(sample["label"] == "scam" for sample in samples)
    assert any(sample["label"] == "benign" for sample in samples)
    modalities = {sample["modality"] for sample in samples}
    assert {"text", "email", "qr"} <= modalities


def test_corpus_ids_are_unique_and_notes_are_present():
    samples = _samples()
    ids = [sample["id"] for sample in samples]
    assert len(ids) == len(set(ids))
    for sample in samples:
        assert sample["notes"], "every sample must explain why it is in the corpus"


def test_every_expected_code_exists_in_the_registry():
    known = signal_codes.known_codes()
    for sample in _samples():
        for code in sample["expect"]:
            assert code in known, "{} expects unregistered code {}".format(sample["id"], code)


def test_corpus_only_references_unroutable_domains():
    """The committed corpus must never contain a live, clickable host.

    RFC 2606 reserves .test/.invalid/.example for exactly this, so a phishing
    sample can be realistic without being dangerous to a careless reader.
    """
    import re

    reserved = (".test", ".invalid", ".example", ".local")
    real_service_hosts = {"bit.ly", "wa.me"}
    first_party = {"example.com", "example.org", "example.net", "example.gov",
                   "example.edu", "google.com", "amazon.com", "netflix.com"}
    host_pattern = re.compile(r"https?://([^/\s:?]+)")
    for sample in _samples():
        for host in host_pattern.findall(sample["content"]):
            lowered = host.lower()
            registrable = ".".join(lowered.split(".")[-2:])
            assert (
                lowered in real_service_hosts
                or registrable in first_party
                or registrable.endswith(reserved)
                or re.match(r"^\d+\.\d+\.\d+\.\d+$", lowered)
            ), "{} references the live host {}".format(sample["id"], host)


def test_harness_produces_no_unmapped_signals():
    observations = [harness.observe(sample) for sample in _samples()]
    metrics = harness.compute_metrics(_samples(), observations)
    assert metrics["unmapped_signals"] == [], (
        "these signals are not registered in signal_codes.py, so they would be "
        "invisible to the metrics: {}".format(metrics["unmapped_signals"])
    )


def test_detectors_catch_their_intended_patterns():
    """Spot checks so a broken detector cannot be 'fixed' by loosening the corpus."""
    observations = {s["id"]: harness.observe(s) for s in _samples()}

    def codes(sample_id):
        return set(observations[sample_id]["codes"])

    assert "url.punycode" in codes("txt-scam-004")
    assert "url.non_ascii_host" in codes("txt-scam-005")
    assert "url.at_masking" in codes("txt-scam-009")
    assert "url.ip_host" in codes("txt-scam-010")
    assert "url.shortener" in codes("txt-scam-003")
    assert "phone.premium_rate" in codes("txt-scam-019")
    assert "phone.brand_country_mismatch" in codes("txt-scam-020")
    assert "text.payment_uri" in codes("txt-scam-018")
    assert "email.spf_fail" in codes("eml-scam-002")
    assert "email.dangerous_attachment" in codes("eml-scam-009")
    assert "qr.payment_payload" in codes("qr-scam-002")
    # Benign controls must stay clean.
    assert codes("txt-ben-006") == set()      # everyday words in a subdomain
    assert codes("txt-ben-009") == set()      # sequential order id, not a phone number
    assert codes("txt-ben-007") == set()      # long, deeply subdominated but real


def test_suspicious_tld_detector_is_covered_by_a_unit_test_instead():
    """Why the TLD rule is not in the corpus: a public repo may not commit one.

    A registrable suspicious TLD (.top, .xyz, ...) inside a sample is a
    clickable phishing-shaped host, so the corpus parks every sample under a
    reserved domain instead. The rule itself is asserted directly here.
    """
    from apps.web.src.app.api.url_analysis import analyze_url

    signals = analyze_url("http://free-crypto-prizes.top/claim")["signals"]
    assert any("suspicious TLD" in signal for signal in signals)


def test_benign_messages_are_not_scored_as_suspicious():
    """The regression the harness exists for: no ordinary message scores >= 50."""
    for sample in _samples():
        if sample["label"] != "benign":
            continue
        score = harness.observe(sample)["score"]
        assert score < 50, "{} is benign but scored {}: {}".format(
            sample["id"], score, sample["content"][:70]
        )


def test_baseline_is_committed_and_current():
    with io.open(BASELINE, encoding="utf-8") as handle:
        baseline = json.load(handle)
    samples = _samples()
    observations = [harness.observe(sample) for sample in samples]
    metrics = harness.compute_metrics(samples, observations)
    regressions = harness.compare_to_baseline(metrics, baseline)
    assert regressions == [], "evaluation regressions: {}".format(regressions)


def test_baseline_metrics_are_at_the_expected_quality():
    with io.open(BASELINE, encoding="utf-8") as handle:
        baseline = json.load(handle)
    assert baseline["detection_rate"] >= 0.9
    assert baseline["false_alarm_rate"] <= 0.05
    assert baseline["score_false_positive_rate"] <= 0.05
    # The whole point of the calibration fix: benign traffic must sit low.
    assert baseline["benign_mean_score"] < 20
    assert baseline["scam_mean_score"] > baseline["benign_mean_score"] + 40
    # Latency is too noisy to gate on relatively, so it gets a loose absolute
    # ceiling instead: a whole-corpus run must stay interactive.
    assert baseline["latency_p95_ms"] < 400
