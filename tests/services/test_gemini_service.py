import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.gemini_service import GeminiService, GeminiResponse, ToolCall


def _make_mock_client(text=None, function_name=None, function_args=None):
    """建立模擬 google.genai Client，可設定回傳文字或 function_call。"""
    mock_part = MagicMock()
    if function_name:
        mock_part.function_call = MagicMock()
        mock_part.function_call.name = function_name
        mock_part.function_call.args = function_args or {}
        mock_part.text = None
    else:
        mock_part.function_call = None
        mock_part.text = text or ''

    mock_candidate = MagicMock()
    mock_candidate.content.parts = [mock_part]

    mock_response = MagicMock()
    mock_response.candidates = [mock_candidate]
    mock_response.text = text or ''

    mock_aio_models = MagicMock()
    mock_aio_models.generate_content = AsyncMock(return_value=mock_response)

    mock_client = MagicMock()
    mock_client.aio.models = mock_aio_models
    return mock_client


@pytest.mark.asyncio
async def test_send_passes_tools_to_generate_content():
    mock_client = _make_mock_client(text='你好！')
    service = GeminiService(client=mock_client)
    await service.send('你好')
    mock_client.aio.models.generate_content.assert_called_once()
    call_kwargs = mock_client.aio.models.generate_content.call_args[1]
    assert 'config' in call_kwargs


@pytest.mark.asyncio
async def test_send_returns_tool_call_when_function_call_in_response():
    mock_client = _make_mock_client(function_name='get_stock_data', function_args={'stock_code': '2330'})
    service = GeminiService(client=mock_client)
    result = await service.send('2330 今天如何')
    assert isinstance(result, GeminiResponse)
    assert result.tool_call is not None
    assert result.tool_call.name == 'get_stock_data'
    assert result.tool_call.args['stock_code'] == '2330'


@pytest.mark.asyncio
async def test_send_returns_text_when_no_function_call():
    mock_client = _make_mock_client(text='今天台股表現平穩。')
    service = GeminiService(client=mock_client)
    result = await service.send('今天股市怎樣')
    assert result.tool_call is None
    assert result.text == '今天台股表現平穩。'


@pytest.mark.asyncio
async def test_send_tool_result_returns_final_text():
    mock_client = _make_mock_client(text='台積電今天收盤900元，上漲5元。')
    service = GeminiService(client=mock_client)
    # 先 send 一次模擬對話歷史
    service._history = []
    result = await service.send_tool_result(
        function_name='get_stock_data',
        result={'stock_code': '2330', 'name': '台積電', 'close': '900.00', 'change': '+5.00'},
    )
    assert result.text == '台積電今天收盤900元，上漲5元。'
    assert result.tool_call is None


@pytest.mark.asyncio
async def test_empty_response_returns_fallback():
    mock_part = MagicMock()
    mock_part.function_call = None
    mock_part.text = ''
    mock_candidate = MagicMock()
    mock_candidate.content.parts = [mock_part]
    mock_response = MagicMock()
    mock_response.candidates = [mock_candidate]

    mock_aio_models = MagicMock()
    mock_aio_models.generate_content = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.aio.models = mock_aio_models

    service = GeminiService(client=mock_client)
    result = await service.send('test')
    assert result.text != ''
    assert result.tool_call is None


@pytest.mark.asyncio
async def test_gemini_exception_propagates():
    mock_aio_models = MagicMock()
    mock_aio_models.generate_content = AsyncMock(side_effect=RuntimeError('API error'))
    mock_client = MagicMock()
    mock_client.aio.models = mock_aio_models

    service = GeminiService(client=mock_client)
    with pytest.raises(RuntimeError):
        await service.send('test')
