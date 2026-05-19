from linebot.v3.messaging import TextMessage
from app.services.twse_service import TWSEDataNotFoundError


async def handle_event(event, line_bot_api, gemini_service, twse_service):
    if getattr(event.message, 'type', None) != 'text':
        return

    user_text = event.message.text
    reply_token = event.reply_token

    gemini_response = await gemini_service.send(user_text)

    if gemini_response.tool_call is None:
        _reply(line_bot_api, reply_token, gemini_response.text)
        return

    tool_call = gemini_response.tool_call

    if tool_call.name == 'get_stock_data':
        stock_code = tool_call.args.get('stock_code', '')
        try:
            stock_data = await twse_service.get_stock_data(stock_code)
        except TWSEDataNotFoundError:
            _reply(line_bot_api, reply_token, f'查無股票代碼 {stock_code} 的資料。')
            return

        final_response = await gemini_service.send_tool_result(
            function_name='get_stock_data',
            result=stock_data,
        )
        _reply(line_bot_api, reply_token, final_response.text)
    else:
        _reply(line_bot_api, reply_token, '抱歉，我不支援這個操作。')


def _reply(line_bot_api, reply_token: str, text: str):
    from linebot.v3.messaging import ReplyMessageRequest
    line_bot_api.reply_message(
        ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=text)])
    )
