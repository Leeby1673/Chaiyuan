import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    line_channel_secret: str
    line_channel_access_token: str
    gemini_api_key: str
    twse_base_url: str


def get_settings() -> Settings:
    def _require(key: str) -> str:
        val = os.environ.get(key)
        if not val:
            raise ValueError(f'Missing required environment variable: {key}')
        return val

    return Settings(
        line_channel_secret=_require('LINE_CHANNEL_SECRET'),
        line_channel_access_token=_require('LINE_CHANNEL_ACCESS_TOKEN'),
        gemini_api_key=_require('GEMINI_API_KEY'),
        twse_base_url=os.environ.get('TWSE_BASE_URL', 'https://openapi.twse.com.tw/v1'),
    )
