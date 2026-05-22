from linebot.v3.messaging import TextMessage
from app.services.twse_service import TWSEDataNotFoundError

_STOCK_PREFIX = '/股價'


async def handle_event(event, line_bot_api, gemini_service, twse_service):
    if getattr(event.message, 'type', None) != 'text':
        return

    user_text = event.message.text
    reply_token = event.reply_token

    if user_text.startswith(_STOCK_PREFIX):
        stock_code = user_text.removeprefix(_STOCK_PREFIX).strip()
        if not stock_code.isdigit():
            _reply(line_bot_api, reply_token, '請輸入股票代碼，例如：/股價 2330')
            return
        await _query_stock_and_reply(reply_token, stock_code, line_bot_api, gemini_service, twse_service)
        return

    gemini_response = await gemini_service.send(user_text)

    if gemini_response.tool_call is None:
        _reply(line_bot_api, reply_token, gemini_response.text)
        return

    tool_call = gemini_response.tool_call

    if tool_call.name == 'get_stock_data':
        stock_code = tool_call.args.get('stock_code', '')
        await _query_stock_and_reply(reply_token, stock_code, line_bot_api, gemini_service, twse_service)
    else:
        _reply(line_bot_api, reply_token, '抱歉，我不支援這個操作。')


async def _query_stock_and_reply(reply_token, stock_code, line_bot_api, gemini_service, twse_service):
    try:
        stock_data = await twse_service.get_stock_data(stock_code)
    except TWSEDataNotFoundError:
        _reply(line_bot_api, reply_token, f'查無股票代碼 {stock_code} 的資料。')
        return

    prompt = (
        f'請用繁體中文簡潔摘要以下股票資料：\n'
        f'股票代碼：{stock_data["stock_code"]}，名稱：{stock_data["name"]}，'
        f'日期：{stock_data["date"]}，收盤價：{stock_data["close"]}，'
        f'漲跌：{stock_data["change"]}，成交量：{stock_data["volume"]}'
    )
    final_response = await gemini_service.send(prompt)
    _reply(line_bot_api, reply_token, final_response.text)


def _reply(line_bot_api, reply_token: str, text: str):
    from linebot.v3.messaging import ReplyMessageRequest
    line_bot_api.reply_message(
        ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=text)])
    )
