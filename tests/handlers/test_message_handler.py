import pytest
from unittest.mock import AsyncMock, MagicMock

from app.handlers.message_handler import handle_event
from app.services.gemini_service import GeminiResponse, ToolCall
from app.services.twse_service import TWSEDataNotFoundError

STOCK_DATA = {
    'stock_code': '2330', 'name': '台積電',
    'date': '113/05/15', 'close': '900.00',
    'volume': '12345678', 'change': '+5.00',
}


def _make_text_event(text: str, reply_token: str = 'fake-token'):
    event = MagicMock()
    event.reply_token = reply_token
    event.message = MagicMock()
    event.message.text = text
    event.message.type = 'text'
    return event


def _make_sticker_event():
    event = MagicMock()
    event.message = MagicMock()
    event.message.type = 'sticker'
    return event


def _make_deps(gemini_response: GeminiResponse, twse_data=None, twse_error=None):
    mock_line_api = MagicMock()
    mock_line_api.reply_message = MagicMock()

    mock_gemini = AsyncMock()
    mock_gemini.send = AsyncMock(return_value=gemini_response)
    mock_gemini.send_tool_result = AsyncMock(
        return_value=GeminiResponse(text='台積電今天收盤900元。')
    )

    mock_twse = AsyncMock()
    if twse_error:
        mock_twse.get_stock_data = AsyncMock(side_effect=twse_error)
    else:
        mock_twse.get_stock_data = AsyncMock(return_value=twse_data or STOCK_DATA)

    return mock_line_api, mock_gemini, mock_twse


def _get_reply_text(line_api) -> str:
    """從 linebot v3 的 ReplyMessageRequest 取出回覆文字。"""
    req = line_api.reply_message.call_args[0][0]
    return req.messages[0].text


@pytest.mark.asyncio
async def test_tool_call_triggers_twse_lookup():
    response = GeminiResponse(text='', tool_call=ToolCall(name='get_stock_data', args={'stock_code': '2330'}))
    line_api, gemini, twse = _make_deps(response)
    event = _make_text_event('2330 今天如何')

    await handle_event(event, line_api, gemini, twse)

    twse.get_stock_data.assert_called_once_with('2330')


@pytest.mark.asyncio
async def test_tool_result_sent_back_to_gemini_and_reply_sent():
    tool_response = GeminiResponse(text='', tool_call=ToolCall(name='get_stock_data', args={'stock_code': '2330'}))
    format_response = GeminiResponse(text='台積電今天收盤900元。')
    line_api, gemini, twse = _make_deps(tool_response)
    gemini.send = AsyncMock(side_effect=[tool_response, format_response])
    event = _make_text_event('2330 今天如何')

    await handle_event(event, line_api, gemini, twse)

    assert gemini.send.call_count == 2
    line_api.reply_message.assert_called_once()
    reply_text = _get_reply_text(line_api)
    assert '900' in reply_text or '台積電' in reply_text


@pytest.mark.asyncio
async def test_direct_text_response_no_service_call():
    response = GeminiResponse(text='今天台股平穩。')
    line_api, gemini, twse = _make_deps(response)
    event = _make_text_event('今天股市怎樣')

    await handle_event(event, line_api, gemini, twse)

    twse.get_stock_data.assert_not_called()
    gemini.send_tool_result.assert_not_called()
    line_api.reply_message.assert_called_once()


@pytest.mark.asyncio
async def test_non_text_event_no_calls():
    line_api = MagicMock()
    gemini = AsyncMock()
    twse = AsyncMock()
    event = _make_sticker_event()

    await handle_event(event, line_api, gemini, twse)

    gemini.send.assert_not_called()
    twse.get_stock_data.assert_not_called()
    line_api.reply_message.assert_not_called()


@pytest.mark.asyncio
async def test_twse_not_found_replies_error_message():
    response = GeminiResponse(text='', tool_call=ToolCall(name='get_stock_data', args={'stock_code': '9999'}))
    line_api, gemini, twse = _make_deps(response, twse_error=TWSEDataNotFoundError('not found'))
    event = _make_text_event('9999')

    await handle_event(event, line_api, gemini, twse)

    line_api.reply_message.assert_called_once()
    reply_text = _get_reply_text(line_api)
    assert '查無' in reply_text or '找不到' in reply_text or '無資料' in reply_text


@pytest.mark.asyncio
async def test_reply_message_called_exactly_once_per_text_event():
    response = GeminiResponse(text='回覆內容。')
    line_api, gemini, twse = _make_deps(response)
    event = _make_text_event('隨便說說')

    await handle_event(event, line_api, gemini, twse)

    assert line_api.reply_message.call_count == 1


@pytest.mark.asyncio
async def test_reply_token_passed_correctly():
    response = GeminiResponse(text='回覆。')
    line_api, gemini, twse = _make_deps(response)
    event = _make_text_event('test', reply_token='my-reply-token')

    await handle_event(event, line_api, gemini, twse)

    req = line_api.reply_message.call_args[0][0]
    assert req.reply_token == 'my-reply-token'


@pytest.mark.asyncio
async def test_unknown_function_call_replies_error():
    response = GeminiResponse(text='', tool_call=ToolCall(name='unknown_function', args={}))
    line_api, gemini, twse = _make_deps(response)
    event = _make_text_event('test')

    await handle_event(event, line_api, gemini, twse)

    line_api.reply_message.assert_called_once()
    reply_text = _get_reply_text(line_api)
    assert len(reply_text) > 0


# --- /股價 快速路徑 ---

@pytest.mark.asyncio
async def test_stock_prefix_skips_first_gemini_send_and_queries_twse():
    line_api, gemini, twse = _make_deps(GeminiResponse(text='宏碁今日收盤18元。'))
    event = _make_text_event('/股價 2330')

    await handle_event(event, line_api, gemini, twse)

    twse.get_stock_data.assert_called_once_with('2330')
    gemini.send_tool_result.assert_not_called()


@pytest.mark.asyncio
async def test_stock_prefix_calls_gemini_send_for_formatting_and_replies():
    line_api, gemini, twse = _make_deps(GeminiResponse(text='宏碁今日收盤18元。'))
    event = _make_text_event('/股價 2330')

    await handle_event(event, line_api, gemini, twse)

    gemini.send.assert_called_once()
    line_api.reply_message.assert_called_once()


@pytest.mark.asyncio
async def test_stock_prefix_with_chinese_replies_hint():
    line_api, gemini, twse = _make_deps(GeminiResponse(text=''))
    event = _make_text_event('/股價 台積電')

    await handle_event(event, line_api, gemini, twse)

    gemini.send.assert_not_called()
    twse.get_stock_data.assert_not_called()
    reply_text = _get_reply_text(line_api)
    assert '2330' in reply_text or '代碼' in reply_text


@pytest.mark.asyncio
async def test_stock_prefix_not_found_replies_error():
    line_api, gemini, twse = _make_deps(
        GeminiResponse(text=''), twse_error=TWSEDataNotFoundError('not found')
    )
    event = _make_text_event('/股價 9999')

    await handle_event(event, line_api, gemini, twse)

    line_api.reply_message.assert_called_once()
    reply_text = _get_reply_text(line_api)
    assert '查無' in reply_text or '找不到' in reply_text or '無資料' in reply_text
