import datetime
import httpx
from app.config import get_settings

TWSE_LEGACY_BASE = 'https://www.twse.com.tw'


class TWSEDataNotFoundError(Exception):
    pass


class TWSEServiceError(Exception):
    pass


async def _get(url: str, params: dict | None = None) -> httpx.Response:
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
    if response.status_code != 200:
        raise TWSEServiceError(f'TWSE API returned status {response.status_code}')
    return response


async def get_stock_data(stock_code: str) -> dict:
    settings = get_settings()
    url = f'{settings.twse_base_url}/exchangeReport/STOCK_DAY_ALL'
    response = await _get(url)

    rows: list[dict] = response.json()
    if not rows:
        raise TWSEDataNotFoundError(f'No data found for stock code: {stock_code}')

    try:
        row = next((r for r in rows if r['Code'] == stock_code), None)
        if row is None:
            raise TWSEDataNotFoundError(f'No data found for stock code: {stock_code}')
        return {
            'stock_code': row['Code'],
            'name': row['Name'],
            'date': row['Date'],
            'close': row['ClosingPrice'],
            'volume': row['TradeVolume'],
            'change': row['Change'],
        }
    except KeyError as e:
        raise TWSEServiceError(f'Unexpected TWSE response format: missing field {e}') from e


async def _latest_trading_payload(url: str, extra_params: dict, max_lookback: int = 7) -> tuple[str, dict]:
    """往回找最近一個交易日，回傳 (date_str, payload)。"""
    for delta in range(max_lookback):
        date_str = (datetime.date.today() - datetime.timedelta(days=delta)).strftime('%Y%m%d')
        response = await _get(url, params={'response': 'json', 'date': date_str, **extra_params})
        payload = response.json()
        if payload.get('stat') == 'OK':
            return date_str, payload
    raise TWSEDataNotFoundError('No trading data found in the last 7 days')


async def get_three_top(top_n: int = 10) -> dict:
    url = f'{TWSE_LEGACY_BASE}/rwd/zh/fund/T86'
    date_str, payload = await _latest_trading_payload(url, {'selectType': 'ALL'})

    fields = payload['fields']
    data = payload['data']

    # 欄位索引
    idx_code = fields.index('證券代號')
    idx_name = fields.index('證券名稱')
    idx_foreign = fields.index('外陸資買賣超股數(不含外資自營商)')
    idx_trust = fields.index('投信買賣超股數')
    idx_dealer = fields.index('自營商買賣超股數')

    def _to_int(val: str) -> int:
        return int(val.replace(',', '').replace('+', ''))

    rows = []
    for row in data:
        try:
            rows.append({
                'code': row[idx_code].strip(),
                'name': row[idx_name].strip(),
                'foreign_net': _to_int(row[idx_foreign]),
                'trust_net': _to_int(row[idx_trust]),
                'dealer_net': _to_int(row[idx_dealer]),
            })
        except (ValueError, IndexError):
            continue

    foreign_top = sorted(rows, key=lambda r: r['foreign_net'], reverse=True)[:top_n]
    trust_top = sorted(rows, key=lambda r: r['trust_net'], reverse=True)[:top_n]
    dealer_top = sorted(rows, key=lambda r: r['dealer_net'], reverse=True)[:top_n]

    return {
        'date': date_str,
        'foreign_top': foreign_top,
        'trust_top': trust_top,
        'dealer_top': dealer_top,
    }


async def get_three_total() -> list[dict]:
    url = f'{TWSE_LEGACY_BASE}/fund/BFI82U'
    _, payload = await _latest_trading_payload(url, {'type': 'day'})

    fields = payload['fields']
    data = payload['data']

    idx_name = fields.index('單位名稱')
    idx_buy = fields.index('買進金額')
    idx_sell = fields.index('賣出金額')
    idx_net = fields.index('買賣差額')

    try:
        return [
            {
                'name': row[idx_name].strip(),
                'buy': row[idx_buy].strip(),
                'sell': row[idx_sell].strip(),
                'net': row[idx_net].strip(),
            }
            for row in data
        ]
    except (KeyError, IndexError) as e:
        raise TWSEServiceError(f'Unexpected BFI82U response format: {e}') from e


async def get_pyp(stock_code: str) -> dict:
    settings = get_settings()
    url = f'{settings.twse_base_url}/exchangeReport/BWIBBU_d'
    response = await _get(url)

    rows: list[dict] = response.json()
    if not rows:
        raise TWSEDataNotFoundError(f'No PYP data found for stock code: {stock_code}')

    try:
        row = next((r for r in rows if r['Code'] == stock_code), None)
        if row is None:
            raise TWSEDataNotFoundError(f'No PYP data found for stock code: {stock_code}')
        return {
            'stock_code': row['Code'],
            'name': row['Name'],
            'date': row['Date'],
            'close': row['ClosePrice'],
            'pe': row['PEratio'],
            'yield_': row['DividendYield'],
            'pb': row['PBratio'],
        }
    except KeyError as e:
        raise TWSEServiceError(f'Unexpected BWIBBU_d response format: missing field {e}') from e
