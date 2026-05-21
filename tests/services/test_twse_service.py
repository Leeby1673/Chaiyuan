import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.twse_service import get_stock_data, TWSEDataNotFoundError

SAMPLE_ROW = {
    'Code': '2330',
    'Name': '台積電',
    'Date': '113/05/15',
    'ClosingPrice': '900.00',
    'TradeVolume': '12345678',
    'Change': '+5.00',
}


def _make_mock_client(status_code=200, json_data=None):
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json = MagicMock(return_value=json_data or [])

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)
    return mock_client


@pytest.mark.asyncio
async def test_returns_correct_dict_for_valid_response():
    mock_client = _make_mock_client(json_data=[SAMPLE_ROW])
    with patch('app.services.twse_service.httpx.AsyncClient', return_value=mock_client):
        result = await get_stock_data('2330')
    assert result['stock_code'] == '2330'
    assert result['name'] == '台積電'
    assert result['date'] == '113/05/15'
    assert result['close'] == '900.00'
    assert result['volume'] == '12345678'
    assert result['change'] == '+5.00'


@pytest.mark.asyncio
async def test_raises_when_empty_list():
    mock_client = _make_mock_client(json_data=[])
    with patch('app.services.twse_service.httpx.AsyncClient', return_value=mock_client):
        with pytest.raises(TWSEDataNotFoundError):
            await get_stock_data('9999')


@pytest.mark.asyncio
async def test_raises_when_stock_code_not_in_list():
    mock_client = _make_mock_client(json_data=[SAMPLE_ROW])  # 只有 2330
    with patch('app.services.twse_service.httpx.AsyncClient', return_value=mock_client):
        with pytest.raises(TWSEDataNotFoundError):
            await get_stock_data('9999')


@pytest.mark.asyncio
async def test_raises_on_http_error():
    mock_client = _make_mock_client(status_code=500, json_data=[])
    with patch('app.services.twse_service.httpx.AsyncClient', return_value=mock_client):
        with pytest.raises(Exception):
            await get_stock_data('2330')



@pytest.mark.asyncio
async def test_request_url_is_stock_day_all():
    mock_client = _make_mock_client(json_data=[SAMPLE_ROW])
    with patch('app.services.twse_service.httpx.AsyncClient', return_value=mock_client):
        await get_stock_data('2330')
    call_url = mock_client.get.call_args[0][0]
    assert 'STOCK_DAY_ALL' in call_url


@pytest.mark.asyncio
async def test_missing_field_raises_graceful_error():
    bad_row = {'Code': '2330'}  # 缺少大部分欄位
    mock_client = _make_mock_client(json_data=[bad_row])
    with patch('app.services.twse_service.httpx.AsyncClient', return_value=mock_client):
        with pytest.raises(Exception) as exc_info:
            await get_stock_data('2330')
    assert 'KeyError' not in type(exc_info.value).__name__
