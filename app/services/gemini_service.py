from dataclasses import dataclass
from google import genai
from google.genai import types as genai_types
from app.config import get_settings

TOOLS = genai_types.Tool(
    function_declarations=[
        genai_types.FunctionDeclaration(
            name='get_stock_data',
            description='查詢台灣股票當日收盤資料',
            parameters=genai_types.Schema(
                type='OBJECT',
                properties={
                    'stock_code': genai_types.Schema(
                        type='STRING',
                        description='4位股票代碼，例如 2330',
                    )
                },
                required=['stock_code'],
            ),
        )
    ]
)

MODEL = 'gemini-3.5-flash'
FALLBACK_TEXT = '抱歉，我現在無法回覆，請稍後再試。'


@dataclass(slots=True)
class ToolCall:
    name: str
    args: dict


@dataclass(slots=True)
class GeminiResponse:
    text: str
    tool_call: ToolCall | None = None


class GeminiService:
    def __init__(self, client=None):
        if client is not None:
            self._client = client
        else:
            settings = get_settings()
            self._client = genai.Client(api_key=settings.gemini_api_key)
        self._history: list[genai_types.Content] = []

    async def send(self, user_text: str) -> GeminiResponse:
        self._history.append(genai_types.Content(role='user', parts=[genai_types.Part(text=user_text)]))
        response = await self._client.aio.models.generate_content(
            model=MODEL,
            contents=self._history,
            config=genai_types.GenerateContentConfig(tools=[TOOLS]),
        )
        return self._parse_response(response)

    async def send_tool_result(self, function_name: str, result: dict) -> GeminiResponse:
        self._history.append(genai_types.Content(
            role='tool',
            parts=[genai_types.Part(
                function_response=genai_types.FunctionResponse(
                    name=function_name,
                    response=result,
                )
            )],
        ))
        response = await self._client.aio.models.generate_content(
            model=MODEL,
            contents=self._history,
            config=genai_types.GenerateContentConfig(tools=[TOOLS]),
        )
        return self._parse_response(response)

    def _parse_response(self, response) -> GeminiResponse:
        try:
            part = response.candidates[0].content.parts[0]
            if part.function_call and part.function_call.name:
                return GeminiResponse(
                    text='',
                    tool_call=ToolCall(
                        name=part.function_call.name,
                        args=dict(part.function_call.args),
                    ),
                )
            text = part.text or ''
            return GeminiResponse(text=text or FALLBACK_TEXT)
        except (IndexError, AttributeError):
            return GeminiResponse(text=FALLBACK_TEXT)
