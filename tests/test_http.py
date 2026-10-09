import httpx
import pytest
import respx

from simplified_auction.config import HttpConfig
from simplified_auction.http import HttpClient, HttpError


@respx.mock
def test_bloqueio_anti_bot_levanta_erro():
    respx.get("https://validate.perfdrive.com/x").mock(
        return_value=httpx.Response(200, text="challenge")
    )
    with (
        HttpClient(HttpConfig(min_interval=0.0)) as client,
        pytest.raises(HttpError, match="anti-bot"),
    ):
        client.get_text("https://validate.perfdrive.com/x")
