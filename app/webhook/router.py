import hashlib
import hmac
import types

from fastapi import APIRouter, HTTPException, Request
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import MessagingApi, ApiClient, Configuration

from app.config import get_settings
from app.handlers.message_handler import handle_event
from app.services.gemini_service import GeminiService
from app.services import twse_service

router = APIRouter()


def _verify_signature(body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).digest().hex()
    return hmac.compare_digest(expected, signature)


@router.post('/webhook')
async def webhook(request: Request):
    settings = get_settings()
    body = await request.body()
    signature = request.headers.get('X-Line-Signature', '')

    if not signature or not _verify_signature(body, signature, settings.line_channel_secret):
        raise HTTPException(status_code=400, detail='Invalid signature')

    parser = WebhookParser(settings.line_channel_secret)
    try:
        events = parser.parse(body.decode('utf-8'), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail='Invalid signature')

    configuration = Configuration(access_token=settings.line_channel_access_token)
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        for event in events:
            gemini = GeminiService()
            await handle_event(event, line_bot_api, gemini, twse_service)

    return {'status': 'ok'}
