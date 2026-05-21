import base64
import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

CHANNEL_SECRET = 'test-channel-secret'
CHANNEL_TOKEN = 'test-channel-token'
GEMINI_KEY = 'test-gemini-key'


def _compute_signature(body: bytes, secret: str) -> str:
    return base64.b64encode(
        hmac.new(secret.encode('utf-8'), body, hashlib.sha256).digest()
    ).decode('utf-8')


def _make_text_payload(text: str = 'hello') -> bytes:
    payload = {
        'destination': 'Utest',
        'events': [
            {
                'type': 'message',
                'replyToken': 'fake-reply-token',
                'source': {'type': 'user', 'userId': 'Utest'},
                'timestamp': 1234567890,
                'message': {'id': '1', 'type': 'text', 'text': text},
            }
        ],
    }
    return json.dumps(payload).encode('utf-8')


def _make_empty_payload() -> bytes:
    return json.dumps({'destination': 'Utest', 'events': []}).encode('utf-8')


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv('LINE_CHANNEL_SECRET', CHANNEL_SECRET)
    monkeypatch.setenv('LINE_CHANNEL_ACCESS_TOKEN', CHANNEL_TOKEN)
    monkeypatch.setenv('GEMINI_API_KEY', GEMINI_KEY)
    app = create_app()
    return TestClient(app)


def _webhook_patches():
    """公用 context managers：mock 掉所有外部依賴。"""
    return (
        patch('app.webhook.router.WebhookParser'),
        patch('app.webhook.router.ApiClient'),
        patch('app.webhook.router.MessagingApi'),
        patch('app.webhook.router.GeminiService'),
        patch('app.webhook.router.handle_event', new=AsyncMock()),
    )


def test_health_endpoint(client):
    resp = client.get('/health')
    assert resp.status_code == 200
    assert resp.json() == {'status': 'ok'}


def test_valid_signature_returns_200(client):
    body = _make_text_payload()
    sig = _compute_signature(body, CHANNEL_SECRET)

    with patch('app.webhook.router.WebhookParser') as MockParser, \
         patch('app.webhook.router.ApiClient'), \
         patch('app.webhook.router.MessagingApi'), \
         patch('app.webhook.router.GeminiService'), \
         patch('app.webhook.router.handle_event', new=AsyncMock()):
        MockParser.return_value.parse.return_value = [MagicMock()]
        resp = client.post(
            '/webhook',
            content=body,
            headers={'X-Line-Signature': sig, 'Content-Type': 'application/json'},
        )
    assert resp.status_code == 200


def test_invalid_signature_returns_400(client):
    from linebot.v3.exceptions import InvalidSignatureError
    body = _make_text_payload()
    with patch('app.webhook.router.WebhookParser') as MockParser:
        MockParser.return_value.parse.side_effect = InvalidSignatureError()
        resp = client.post(
            '/webhook',
            content=body,
            headers={'X-Line-Signature': 'bad-signature', 'Content-Type': 'application/json'},
        )
    assert resp.status_code == 400


def test_missing_signature_returns_400(client):
    body = _make_text_payload()
    resp = client.post('/webhook', content=body, headers={'Content-Type': 'application/json'})
    assert resp.status_code == 400


def test_one_event_calls_handle_event_once(client):
    body = _make_text_payload()
    sig = _compute_signature(body, CHANNEL_SECRET)

    with patch('app.webhook.router.WebhookParser') as MockParser, \
         patch('app.webhook.router.ApiClient'), \
         patch('app.webhook.router.MessagingApi'), \
         patch('app.webhook.router.GeminiService'), \
         patch('app.webhook.router.handle_event', new=AsyncMock()) as mock_handle:
        MockParser.return_value.parse.return_value = [MagicMock()]
        client.post(
            '/webhook',
            content=body,
            headers={'X-Line-Signature': sig, 'Content-Type': 'application/json'},
        )
    assert mock_handle.call_count == 1


def test_two_events_calls_handle_event_twice(client):
    body = _make_text_payload()
    sig = _compute_signature(body, CHANNEL_SECRET)

    with patch('app.webhook.router.WebhookParser') as MockParser, \
         patch('app.webhook.router.ApiClient'), \
         patch('app.webhook.router.MessagingApi'), \
         patch('app.webhook.router.GeminiService'), \
         patch('app.webhook.router.handle_event', new=AsyncMock()) as mock_handle:
        MockParser.return_value.parse.return_value = [MagicMock(), MagicMock()]
        client.post(
            '/webhook',
            content=body,
            headers={'X-Line-Signature': sig, 'Content-Type': 'application/json'},
        )
    assert mock_handle.call_count == 2


def test_empty_events_returns_200_no_handle(client):
    body = _make_empty_payload()
    sig = _compute_signature(body, CHANNEL_SECRET)

    with patch('app.webhook.router.WebhookParser') as MockParser, \
         patch('app.webhook.router.ApiClient'), \
         patch('app.webhook.router.MessagingApi'), \
         patch('app.webhook.router.GeminiService'), \
         patch('app.webhook.router.handle_event', new=AsyncMock()) as mock_handle:
        MockParser.return_value.parse.return_value = []
        resp = client.post(
            '/webhook',
            content=body,
            headers={'X-Line-Signature': sig, 'Content-Type': 'application/json'},
        )
    assert resp.status_code == 200
    mock_handle.assert_not_called()
