from fastapi.testclient import TestClient

from apps.web.src.app.api.url_analysis import analyze_url, analyze_urls
from apps.web.src.app.main import app

client = TestClient(app)


CYRILLIC_LOOKALIKE = "http://\u0440\u0430ypal.com/login"


def test_clean_https_url_produces_no_signals():
    result = analyze_url("https://www.google.com/search?q=cats")
    assert result["signals"] == []
    assert result["score_delta"] == 0


def test_paypal_help_page_is_clean():
    assert analyze_url("https://www.paypal.com/help")["signals"] == []


def test_suspicious_tld_and_credential_path_raise_score():
    result = analyze_url("http://free-crypto-prizes.top/claim")
    assert any("suspicious TLD" in signal for signal in result["signals"])
    assert any("credential-themed path" in signal for signal in result["signals"])
    assert result["score_delta"] >= 40


def test_punycode_and_homoglyph_hosts_are_flagged():
    punycode = analyze_url("http://xn--pypal-4ve.com/login")
    assert any("punycode" in signal for signal in punycode["signals"])

    homoglyph = analyze_url(CYRILLIC_LOOKALIKE)
    assert any("non-ASCII" in signal for signal in homoglyph["signals"])


def test_shortener_is_flagged():
    assert any("shortener" in signal for signal in analyze_url("http://bit.ly/3xYzQ1")["signals"])


def test_brand_lookalike_detected():
    result = analyze_url("http://paypal.com.secure-login.xyz/verify")
    joined = " | ".join(result["signals"])
    assert "paypal" in joined
    assert "suspicious TLD" in joined


def test_digit_swapped_brand_is_detected():
    joined = " | ".join(analyze_url("http://paypa1.com/login")["signals"])
    assert "paypal" in joined


def test_everyday_words_are_not_treated_as_lookalikes():
    assert analyze_url("https://apply-now.example.com")["signals"] == []


def test_ip_host_and_at_sign_masking_are_flagged():
    assert any("IP address" in signal for signal in analyze_url("http://192.168.1.10/login")["signals"])
    assert any(
        "masking" in signal for signal in analyze_url("http://google.com@evil-site.xyz/")["signals"]
    )


def test_analyze_urls_uses_the_worst_single_url():
    scan = analyze_urls(["https://google.com", "http://free-prizes.top"])
    assert len(scan["results"]) == 2
    assert scan["score_delta"] > 0


def test_check_endpoint_surfaces_url_signals_in_evidence():
    response = client.post(
        "/check", json={"content": "Claim now at http://free-crypto-prizes.top/claim"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert "suspicious TLD" in payload["evidence"]
    assert payload["risk_score"] >= 70