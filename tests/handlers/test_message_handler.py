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

PYP_DATA = {
    'stock_code': '2330', 'name': '台積電',
    'date': '20260522', 'close': '900.00',
    'pe': '20.5', 'yield_': '1.50', 'pb': '5.2',
}

THREE_TOP_DATA = {
    'date': '20260522',
    'foreign_top': [{'code': '2330', 'name': '台積電', 'foreign_net': 1000000}],
    'trust_top':   [{'code': '2330', 'name': '台積電', 'trust_net': 200000}],
    'dealer_top':  [{'code': '2330', 'name': '台積電', 'dealer_net': 50000}],
}

THREE_TOTAL_DATA = [
    {'name': '外陸資', 'buy': '8,000,000', 'sell': '7,000,000', 'net': '+1,000,000'},
    {'name': '三大法人合計', 'buy': '9,500,000', 'sell': '8,300,000', 'net': '+1,200,000'},
]


def _make_text_event(text: str, reply_token: str = 'fake-token', source_type: str = 'user'):
    event = MagicMock()
    event.reply_token = reply_token
    event.message = MagicMock()
    event.message.text = text
    event.message.type = 'text'
    event.source = MagicMock()
    event.source.type = source_type
    return event


def _make_group_event(text: str, reply_token: str = 'fake-token'):
    return _make_text_event(text, reply_token, source_type='group')


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
    mock_twse.get_three_top = AsyncMock(return_value=THREE_TOP_DATA)
    mock_twse.get_three_total = AsyncMock(return_value=THREE_TOTAL_DATA)
    mock_twse.get_pyp = AsyncMock(return_value=PYP_DATA)

    return mock_line_api, mock_gemini, mock_twse


def _get_reply_text(line_api) -> str:
    req = line_api.reply_message.call_args[0][0]
    return req.messages[0].text


# --- 私訊：原有行為 ---

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

    assert gemini.send.call_count == 1  # 只有第一次判斷意圖，/price 已改用 Flex
    line_api.reply_message.assert_called_once()


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


# --- 群組靜默邏輯 ---

@pytest.mark.asyncio
async def test_group_non_command_is_silent():
    line_api, gemini, twse = _make_deps(GeminiResponse(text=''))
    event = _make_group_event('今天天氣怎樣')

    await handle_event(event, line_api, gemini, twse)

    gemini.send.assert_not_called()
    line_api.reply_message.assert_not_called()


@pytest.mark.asyncio
async def test_group_unknown_command_is_silent():
    line_api, gemini, twse = _make_deps(GeminiResponse(text=''))
    event = _make_group_event('/unknown 123')

    await handle_event(event, line_api, gemini, twse)

    gemini.send.assert_not_called()
    line_api.reply_message.assert_not_called()


@pytest.mark.asyncio
async def test_dm_non_command_goes_to_gemini():
    response = GeminiResponse(text='你好！')
    line_api, gemini, twse = _make_deps(response)
    event = _make_text_event('你好')  # 私訊，source_type='user'

    await handle_event(event, line_api, gemini, twse)

    gemini.send.assert_called_once()
    line_api.reply_message.assert_called_once()


# --- /price 指令 ---

@pytest.mark.asyncio
async def test_price_command_queries_twse_and_replies():
    line_api, gemini, twse = _make_deps(GeminiResponse(text='台積電收盤900元。'))
    event = _make_group_event('/price 2330')

    await handle_event(event, line_api, gemini, twse)

    twse.get_stock_data.assert_called_once_with('2330')
    gemini.send.assert_not_called()
    line_api.reply_message.assert_called_once()


@pytest.mark.asyncio
async def test_price_command_with_chinese_replies_hint():
    line_api, gemini, twse = _make_deps(GeminiResponse(text=''))
    event = _make_group_event('/price 台積電')

    await handle_event(event, line_api, gemini, twse)

    twse.get_stock_data.assert_not_called()
    reply_text = _get_reply_text(line_api)
    assert '2330' in reply_text or '代碼' in reply_text


# --- /threetop 指令 ---

@pytest.mark.asyncio
async def test_threetop_command_calls_service_and_replies():
    line_api, gemini, twse = _make_deps(GeminiResponse(text=''))
    event = _make_group_event('/threetop')

    await handle_event(event, line_api, gemini, twse)

    twse.get_three_top.assert_called_once()
    line_api.reply_message.assert_called_once()
    reply_text = _get_reply_text(line_api)
    assert '外資' in reply_text
    assert '投信' in reply_text
    assert '自營商' in reply_text


# --- /threetotal 指令 ---

@pytest.mark.asyncio
async def test_threetotal_command_calls_service_and_replies():
    line_api, gemini, twse = _make_deps(GeminiResponse(text=''))
    event = _make_group_event('/threetotal')

    await handle_event(event, line_api, gemini, twse)

    twse.get_three_total.assert_called_once()
    line_api.reply_message.assert_called_once()
    reply_text = _get_reply_text(line_api)
    assert '三大法人' in reply_text or '外陸資' in reply_text


# --- /pyp 指令 ---

@pytest.mark.asyncio
async def test_pyp_command_returns_pe_yield_pb():
    line_api, gemini, twse = _make_deps(GeminiResponse(text=''))
    event = _make_group_event('/pyp 2330')

    await handle_event(event, line_api, gemini, twse)

    twse.get_pyp.assert_called_once_with('2330')
    line_api.reply_message.assert_called_once()
    reply_text = _get_reply_text(line_api)
    assert 'PE' in reply_text or '本益比' in reply_text
    assert 'Yield' in reply_text or '殖利率' in reply_text
    assert 'PB' in reply_text or '淨值比' in reply_text


@pytest.mark.asyncio
async def test_pyp_command_with_chinese_replies_hint():
    line_api, gemini, twse = _make_deps(GeminiResponse(text=''))
    event = _make_group_event('/pyp 台積電')

    await handle_event(event, line_api, gemini, twse)

    twse.get_pyp.assert_not_called()
    reply_text = _get_reply_text(line_api)
    assert '代碼' in reply_text or '2330' in reply_text


# --- /qa 指令 ---

@pytest.mark.asyncio
async def test_qa_command_sends_question_to_gemini_and_replies():
    line_api, gemini, twse = _make_deps(GeminiResponse(text='本益比是股價除以每股盈餘。'))
    event = _make_group_event('/qa 什麼是本益比')

    await handle_event(event, line_api, gemini, twse)

    gemini.send.assert_called_once_with('什麼是本益比')
    line_api.reply_message.assert_called_once()
    assert '本益比' in _get_reply_text(line_api)


@pytest.mark.asyncio
async def test_qa_command_empty_question_replies_hint():
    line_api, gemini, twse = _make_deps(GeminiResponse(text=''))
    event = _make_group_event('/qa')

    await handle_event(event, line_api, gemini, twse)

    gemini.send.assert_not_called()
    reply_text = _get_reply_text(line_api)
    assert '問題' in reply_text or '/qa' in reply_text


# --- /help 指令 ---

@pytest.mark.asyncio
async def test_help_command_lists_all_commands():
    line_api, gemini, twse = _make_deps(GeminiResponse(text=''))
    event = _make_group_event('/help')

    await handle_event(event, line_api, gemini, twse)

    line_api.reply_message.assert_called_once()
    reply_text = _get_reply_text(line_api)
    assert '/price' in reply_text
    assert '/threetop' in reply_text
    assert '/threetotal' in reply_text
    assert '/pyp' in reply_text
    assert '/qa' in reply_text
    assert '/help' in reply_text
