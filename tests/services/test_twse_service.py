import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.twse_service import (
    get_stock_data, get_three_top, get_three_total, get_pyp,
    TWSEDataNotFoundError,
)

SAMPLE_ROW = {
    'Code': '2330',
    'Name': '台積電',
    'Date': '113/05/15',
    'ClosingPrice': '900.00',
    'TradeVolume': '12345678',
    'Change': '+5.00',
}

SAMPLE_BWIBBU_ROW = {
    'Date': '20260522',
    'Code': '2330',
    'Name': '台積電',
    'ClosePrice': '900.00',
    'DividendYield': '1.50',
    'DividendYear': '114',
    'PEratio': '20.5',
    'PBratio': '5.2',
    'FiscalYearQuarter': '2026Q1',
}

T86_FIELDS = [
    '證券代號', '證券名稱',
    '外陸資買賣超股數(不含外資自營商)',
    '外資自營商買賣超股數',
    '投信買賣超股數',
    '自營商買賣超股數',
    '三大法人買賣超股數',
]

T86_DATA = [
    ['2330', '台積電', '+1,000,000', '+50,000', '+200,000', '+30,000', '+1,280,000'],
    ['2454', '聯發科', '+800,000',  '+20,000', '+150,000', '+10,000', '+980,000'],
]

BFI82U_FIELDS = ['單位名稱', '買進金額', '賣出金額', '買賣差額']
BFI82U_DATA = [
    ['自營商－自行買賣', '1,000,000', '900,000', '+100,000'],
    ['投信',            '500,000',   '400,000', '+100,000'],
    ['外陸資',          '8,000,000', '7,000,000', '+1,000,000'],
    ['三大法人合計',    '9,500,000', '8,300,000', '+1,200,000'],
]


def _make_mock_client(status_code=200, json_data=None):
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json = MagicMock(return_value=json_data or [])

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)
    return mock_client


# --- get_stock_data ---

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
    mock_client = _make_mock_client(json_data=[SAMPLE_ROW])
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
    bad_row = {'Code': '2330'}
    mock_client = _make_mock_client(json_data=[bad_row])
    with patch('app.services.twse_service.httpx.AsyncClient', return_value=mock_client):
        with pytest.raises(Exception) as exc_info:
            await get_stock_data('2330')
    assert 'KeyError' not in type(exc_info.value).__name__


# --- get_three_top ---

@pytest.mark.asyncio
async def test_three_top_returns_foreign_trust_and_dealer_lists():
    payload = {'stat': 'OK', 'fields': T86_FIELDS, 'data': T86_DATA}
    mock_client = _make_mock_client(json_data=payload)
    with patch('app.services.twse_service.httpx.AsyncClient', return_value=mock_client):
        result = await get_three_top(top_n=10)
    assert 'foreign_top' in result
    assert 'trust_top' in result
    assert 'dealer_top' in result
    assert result['foreign_top'][0]['code'] == '2330'
    assert result['trust_top'][0]['code'] == '2330'
    assert result['dealer_top'][0]['code'] == '2330'


@pytest.mark.asyncio
async def test_three_top_respects_top_n():
    many_rows = [[str(i), f'股票{i}', f'+{i*1000}', '+0', f'+{i*500}', '+0', '+0']
                 for i in range(1, 20)]
    payload = {'stat': 'OK', 'fields': T86_FIELDS, 'data': many_rows}
    mock_client = _make_mock_client(json_data=payload)
    with patch('app.services.twse_service.httpx.AsyncClient', return_value=mock_client):
        result = await get_three_top(top_n=5)
    assert len(result['foreign_top']) == 5
    assert len(result['trust_top']) == 5


@pytest.mark.asyncio
async def test_three_top_raises_when_stat_not_ok():
    payload = {'stat': 'NO DATA'}
    mock_client = _make_mock_client(json_data=payload)
    with patch('app.services.twse_service.httpx.AsyncClient', return_value=mock_client):
        with pytest.raises(TWSEDataNotFoundError):
            await get_three_top()


# --- get_three_total ---

@pytest.mark.asyncio
async def test_three_total_returns_all_rows():
    payload = {'stat': 'OK', 'fields': BFI82U_FIELDS, 'data': BFI82U_DATA}
    mock_client = _make_mock_client(json_data=payload)
    with patch('app.services.twse_service.httpx.AsyncClient', return_value=mock_client):
        result = await get_three_total()
    assert len(result) == 4
    assert result[0]['name'] == '自營商－自行買賣'
    assert result[-1]['name'] == '三大法人合計'


@pytest.mark.asyncio
async def test_three_total_raises_when_stat_not_ok():
    payload = {'stat': 'NO DATA'}
    mock_client = _make_mock_client(json_data=payload)
    with patch('app.services.twse_service.httpx.AsyncClient', return_value=mock_client):
        with pytest.raises(TWSEDataNotFoundError):
            await get_three_total()


# --- get_pyp ---

@pytest.mark.asyncio
async def test_pyp_returns_correct_fields():
    mock_client = _make_mock_client(json_data=[SAMPLE_BWIBBU_ROW])
    with patch('app.services.twse_service.httpx.AsyncClient', return_value=mock_client):
        result = await get_pyp('2330')
    assert result['stock_code'] == '2330'
    assert result['pe'] == '20.5'
    assert result['yield_'] == '1.50'
    assert result['pb'] == '5.2'


@pytest.mark.asyncio
async def test_pyp_raises_when_code_not_found():
    mock_client = _make_mock_client(json_data=[SAMPLE_BWIBBU_ROW])
    with patch('app.services.twse_service.httpx.AsyncClient', return_value=mock_client):
        with pytest.raises(TWSEDataNotFoundError):
            await get_pyp('9999')
