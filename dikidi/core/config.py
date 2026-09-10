import re
from dataclasses import dataclass


BASE_URL = "https://dikidi.ru"
AUTH_URL = "https://auth.dikidi.ru"
QUERY_URL = "https://query.dikidi.ru"
NET_URL = "https://dikidi.net"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/152.0.0.0 Safari/537.36"
)

CRITICAL_COOKIES = ["token", "cookie_name", "uac", "cid", "session", "lang", "XSRF-TOKEN"]


@dataclass(frozen=True)
class DikidiConfig:
    phone: str
    password: str
    company_id: str
    session_file: str = "session_cookies.json"
    timeout: float = 25.0

    @property
    def clean_phone(self) -> str:
        return re.sub(r"\D", "", str(self.phone))