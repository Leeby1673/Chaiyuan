import httpx
from app.config import get_settings


class TWSEDataNotFoundError(Exception):
    pass


class TWSEServiceError(Exception):
    pass


async def get_stock_data(stock_code: str) -> dict:
    settings = get_settings()
    url = f'{settings.twse_base_url}/exchangeReport/STOCK_DAY_ALL'

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    if response.status_code != 200:
        raise TWSEServiceError(f'TWSE API returned status {response.status_code}')

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
