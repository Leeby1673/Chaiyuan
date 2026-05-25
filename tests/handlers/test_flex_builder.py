from app.handlers.flex_builder import build_price

STOCK_DATA = {
    'stock_code': '2330',
    'name': '台積電',
    'date': '113/05/15',
    'close': '900.00',
    'volume': '12345678',
    'change': '+5.00',
}


def test_build_price_returns_bubble():
    result = build_price(STOCK_DATA)
    assert result['type'] == 'bubble'


def test_build_price_contains_stock_code_and_name():
    result = build_price(STOCK_DATA)
    header_text = result['header']['contents'][0]['text']
    assert '2330' in header_text
    assert '台積電' in header_text


def test_build_price_contains_close_price():
    result = build_price(STOCK_DATA)
    body_texts = [c['text'] for c in result['body']['contents'][0]['contents']]
    assert any('900' in t for t in body_texts)


def test_build_price_positive_change_is_red():
    result = build_price(STOCK_DATA)
    change_item = result['body']['contents'][0]['contents'][1]
    assert change_item['color'] == '#e53935'


def test_build_price_negative_change_is_green():
    neg_data = {**STOCK_DATA, 'change': '-5.00'}
    result = build_price(neg_data)
    change_item = result['body']['contents'][0]['contents'][1]
    assert change_item['color'] == '#43a047'


def test_build_price_volume_formatted():
    result = build_price(STOCK_DATA)
    volume_row = result['body']['contents'][2]
    volume_text = volume_row['contents'][1]['text']
    assert '萬' in volume_text or '億' in volume_text or '股' in volume_text
