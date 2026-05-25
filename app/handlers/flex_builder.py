def build_price(stock_data: dict) -> dict:
    close = stock_data['close']
    change = stock_data['change']
    change_color = '#e53935' if not change.startswith('-') else '#43a047'

    return {
        'type': 'bubble',
        'size': 'kilo',
        'header': {
            'type': 'box',
            'layout': 'vertical',
            'backgroundColor': '#1a1a2e',
            'paddingAll': '16px',
            'contents': [
                {
                    'type': 'text',
                    'text': f'{stock_data["stock_code"]} {stock_data["name"]}',
                    'color': '#ffffff',
                    'size': 'md',
                    'weight': 'bold',
                },
                {
                    'type': 'text',
                    'text': stock_data['date'],
                    'color': '#aaaaaa',
                    'size': 'sm',
                    'margin': 'sm',
                },
            ],
        },
        'body': {
            'type': 'box',
            'layout': 'vertical',
            'paddingAll': '16px',
            'contents': [
                {
                    'type': 'box',
                    'layout': 'horizontal',
                    'contents': [
                        {
                            'type': 'text',
                            'text': f'${close}',
                            'size': 'xxl',
                            'weight': 'bold',
                            'color': '#1a1a2e',
                            'flex': 1,
                        },
                        {
                            'type': 'text',
                            'text': change if change.startswith(('+', '-')) else f'+{change}',
                            'size': 'xl',
                            'weight': 'bold',
                            'color': change_color,
                            'align': 'end',
                            'gravity': 'center',
                        },
                    ],
                },
                {
                    'type': 'separator',
                    'margin': 'md',
                    'color': '#eeeeee',
                },
                {
                    'type': 'box',
                    'layout': 'horizontal',
                    'margin': 'md',
                    'contents': [
                        {
                            'type': 'text',
                            'text': '成交量',
                            'size': 'sm',
                            'color': '#888888',
                            'flex': 1,
                        },
                        {
                            'type': 'text',
                            'text': _fmt_volume(stock_data['volume']),
                            'size': 'sm',
                            'color': '#333333',
                            'align': 'end',
                        },
                    ],
                },
            ],
        },
    }


def _fmt_volume(volume: str) -> str:
    try:
        v = int(volume.replace(',', ''))
        if v >= 100_000_000:
            return f'{v / 100_000_000:.1f} 億股'
        if v >= 10_000:
            return f'{v / 10_000:.1f} 萬股'
        return f'{v:,} 股'
    except ValueError:
        return volume
