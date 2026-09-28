import pytest

from apps.web.src.app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.mark.parametrize(
    'content, expected_score, expected_evidence, expected_level',
    [
        ('This is a message about ExampleBrand.', 10, 'Trusted brand detected.', 'low'),
        ('This is a message about TestBrand.', 50, 'Untrusted brand detected.', 'suspicious'),
        ('No brand mentioned here.', 0, 'Content appears to be normal text.', 'low'),
        ('Please open http://example.com now.', 70, 'Detected a URL in the content.', 'high'),
    ],
)
def test_analyze_content(content, expected_score, expected_evidence, expected_level):
    response = client.post('/check', json={'content': content})
    assert response.status_code == 200

    payload = response.json()
    assert payload['analysis_id']
    assert payload['created_at']
    assert payload['risk_score'] == expected_score
    assert expected_evidence in payload['evidence']
    assert payload['risk_level'] == expected_level

    stored = client.get(f"/analyses/{payload['analysis_id']}")
    assert stored.status_code == 200
    assert stored.json()['analysis_id'] == payload['analysis_id']
    assert stored.json()['risk_score'] == expected_score

    history = client.get('/api/v1/me/analyses')
    assert history.status_code == 200
    assert any(item['analysis_id'] == payload['analysis_id'] for item in history.json())
