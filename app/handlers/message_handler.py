from linebot.v3.messaging import TextMessage, FlexMessage, FlexContainer
from app.services.twse_service import TWSEDataNotFoundError, TWSEServiceError
from app.handlers.flex_builder import build_price

_COMMANDS = {'/price', '/threetop', '/threetotal', '/pyp', '/qa', '/help'}

_HELP_TEXT = (
    '財猿可用指令：\n'
    '/price <代號>    查詢收盤價，例如 /price 2330\n'
    '/threetop        外資、投信當日個股買超前 10 名\n'
    '/threetotal      三大法人大盤今日買賣超合計\n'
    '/pyp <代號>      本益比、殖利率、股價淨值比，例如 /pyp 2330\n'
    '/qa <問題>       向 AI 提問，例如 /qa 什麼是本益比\n'
    '/help            顯示此說明'
)


def _is_group(event) -> bool:
    return getattr(event.source, 'type', None) == 'group'


def _command_of(text: str) -> str | None:
    cmd = text.split()[0].lower() if text.strip() else ''
    return cmd if cmd in _COMMANDS else None


async def handle_event(event, line_bot_api, gemini_service, twse_service):
    if getattr(event.message, 'type', None) != 'text':
        return

    user_text = event.message.text.strip()
    reply_token = event.reply_token

    cmd = _command_of(user_text)

    if _is_group(event) and cmd is None:
        return  # 群組裡非指令訊息完全靜默

    if cmd == '/price':
        stock_code = user_text.split()[1] if len(user_text.split()) > 1 else ''
        if not stock_code.isdigit():
            _reply(line_bot_api, reply_token, '請輸入股票代碼，例如：/price 2330')
            return
        await _handle_price(reply_token, stock_code, line_bot_api, gemini_service, twse_service)

    elif cmd == '/threetop':
        await _handle_threetop(reply_token, line_bot_api, twse_service)

    elif cmd == '/threetotal':
        await _handle_threetotal(reply_token, line_bot_api, twse_service)

    elif cmd == '/pyp':
        stock_code = user_text.split()[1] if len(user_text.split()) > 1 else ''
        if not stock_code.isdigit():
            _reply(line_bot_api, reply_token, '請輸入股票代碼，例如：/pyp 2330')
            return
        await _handle_pyp(reply_token, stock_code, line_bot_api, twse_service)

    elif cmd == '/qa':
        question = user_text[len('/qa'):].strip()
        if not question:
            _reply(line_bot_api, reply_token, '請輸入問題，例如：/qa 什麼是本益比')
            return
        response = await gemini_service.send(question)
        _reply(line_bot_api, reply_token, response.text)

    elif cmd == '/help':
        _reply(line_bot_api, reply_token, _HELP_TEXT)

    else:
        # 私訊非指令走 Gemini 自由對話
        gemini_response = await gemini_service.send(user_text)
        if gemini_response.tool_call is None:
            _reply(line_bot_api, reply_token, gemini_response.text)
            return
        tool_call = gemini_response.tool_call
        if tool_call.name == 'get_stock_data':
            stock_code = tool_call.args.get('stock_code', '')
            await _handle_price(reply_token, stock_code, line_bot_api, gemini_service, twse_service)
        else:
            _reply(line_bot_api, reply_token, '抱歉，我不支援這個操作。')


async def _handle_price(reply_token, stock_code, line_bot_api, gemini_service, twse_service):
    try:
        stock_data = await twse_service.get_stock_data(stock_code)
    except TWSEDataNotFoundError:
        _reply(line_bot_api, reply_token, f'查無股票代碼 {stock_code} 的資料。')
        return
    alt_text = f'{stock_data["stock_code"]} {stock_data["name"]} {stock_data["close"]}'
    _reply_flex(line_bot_api, reply_token, alt_text, build_price(stock_data))


async def _handle_threetop(reply_token, line_bot_api, twse_service):
    try:
        data = await twse_service.get_three_top()
    except (TWSEDataNotFoundError, TWSEServiceError) as e:
        _reply(line_bot_api, reply_token, f'查詢失敗：{e}')
        return

    def _fmt_rows(rows: list[dict], net_key: str) -> str:
        lines = []
        for i, r in enumerate(rows, 1):
            net = r[net_key]
            sign = '+' if net >= 0 else ''
            lines.append(f'{i:2}. {r["code"]} {r["name"]} {sign}{net:,}')
        return '\n'.join(lines)

    text = (
        f'【三大法人買超 {data["date"]}】\n\n'
        f'▍外資買超前10名（股）\n{_fmt_rows(data["foreign_top"], "foreign_net")}\n\n'
        f'▍投信買超前10名（股）\n{_fmt_rows(data["trust_top"], "trust_net")}\n\n'
        f'▍自營商買超前10名（股）\n{_fmt_rows(data["dealer_top"], "dealer_net")}'
    )
    _reply(line_bot_api, reply_token, text)


async def _handle_threetotal(reply_token, line_bot_api, twse_service):
    try:
        rows = await twse_service.get_three_total()
    except (TWSEDataNotFoundError, TWSEServiceError) as e:
        _reply(line_bot_api, reply_token, f'查詢失敗：{e}')
        return

    lines = ['【三大法人大盤買賣超】（千元）\n']
    for r in rows:
        lines.append(f'{r["name"]}\n  買：{r["buy"]}　賣：{r["sell"]}　淨：{r["net"]}')
    _reply(line_bot_api, reply_token, '\n'.join(lines))


async def _handle_pyp(reply_token, stock_code, line_bot_api, twse_service):
    try:
        data = await twse_service.get_pyp(stock_code)
    except TWSEDataNotFoundError:
        _reply(line_bot_api, reply_token, f'查無股票代碼 {stock_code} 的資料。')
        return
    pe = data['pe'] or 'N/A'
    text = (
        f'【{data["stock_code"]} {data["name"]}】 {data["date"]}\n'
        f'收盤價：{data["close"]}\n'
        f'本益比（PE）：{pe}\n'
        f'殖利率（Yield）：{data["yield_"]}%\n'
        f'股價淨值比（PB）：{data["pb"]}'
    )
    _reply(line_bot_api, reply_token, text)


def _reply(line_bot_api, reply_token: str, text: str):
    from linebot.v3.messaging import ReplyMessageRequest
    line_bot_api.reply_message(
        ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=text)])
    )


def _reply_flex(line_bot_api, reply_token: str, alt_text: str, contents: dict):
    from linebot.v3.messaging import ReplyMessageRequest
    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[FlexMessage(alt_text=alt_text, contents=FlexContainer.from_dict(contents))],
        )
    )
