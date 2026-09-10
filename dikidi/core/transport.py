import logging
import time
from typing import Any
import httpx
from dikidi.core.config import DEFAULT_USER_AGENT, NET_URL, QUERY_URL, DikidiConfig
from dikidi.core.token_storage import TokenStorage
from dikidi.auth.flow import AuthFlow
from dikidi.core.guards import guard_http_response

logger = logging.getLogger("DikidiTransport")


class DikidiTransport:
    """Устойчивый транспорт с авто-восстановлением сессии, пробросом XSRF и стражами."""

    def __init__(self, config: DikidiConfig):
        self.config = config
        self.storage = TokenStorage(config.session_file)
        self.user_id: str | None = None

        self.session = httpx.Client(
            http2=True,
            timeout=config.timeout,
            headers={
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
                "Origin": NET_URL,
                "Referer": f"{NET_URL}/ru/owner/journal/?company={self.config.company_id}",
            },
        )
        self._init_session()

    def _init_session(self) -> None:
        loaded, user_id = self.storage.load(self.session.cookies)
        if loaded:
            self.user_id = user_id

    def get_xsrf_token(self) -> str | None:
        for c in self.session.cookies.jar:
            if c.name == "XSRF-TOKEN":
                return c.value
        return None

    def get_ajax_headers(self, referer_path: str | None = None) -> dict[str, str]:
        ref = referer_path or f"/ru/owner/journal/?company={self.config.company_id}"
        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": NET_URL,
            "Referer": f"{NET_URL}{ref}" if not ref.startswith("http") else ref,
        }
        xsrf = self.get_xsrf_token()
        if xsrf:
            headers["X-XSRF-TOKEN"] = xsrf
        return headers

    def is_session_alive(self) -> bool:
        try:
            resp = self.session.get(
                f"{QUERY_URL}/timeline/count/",
                headers={"Accept": "application/json, text/javascript, */*; q=0.01"},
            )
            return resp.status_code == 200
        except Exception as e:
            logger.warning("[HEARTBEAT] Ошибка проверки сессии: %s", e)
            return False

    def login(self) -> None:
        self.user_id = AuthFlow.login(
            client=self.session,
            phone=self.config.clean_phone,
            password=self.config.password,
            company_id=self.config.company_id,
        )
        self.storage.save(self.session.cookies, self.user_id)

    def ensure_auth(self) -> None:
        has_session_cookie = any(c.name in ("session", "uac") for c in self.session.cookies.jar)
        if not has_session_cookie or not self.is_session_alive():
            logger.info("[AUTH] Сессия недействительна. Выполняется вход...")
            self.login()

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        self.ensure_auth()
        t0 = time.time()
        logger.info("[HTTP] >> %s %s", method.upper(), url)

        resp = self.session.request(method, url, **kwargs)
        duration = int((time.time() - t0) * 1000)

        preview = resp.text[:250].strip() if resp.text else "<пустой ответ>"
        logger.info("[HTTP] << %d %s (%d ms) | %s", resp.status_code, resp.reason_phrase, duration, preview)

        # 1. Проверка на устаревание сессии (401/403 или "Недостаточно прав")
        is_expired = False
        if resp.status_code in (401, 403):
            is_expired = True
        else:
            try:
                payload = resp.json()
                if isinstance(payload, dict) and payload.get("error") == 1:
                    if "Недостаточно прав" in payload.get("message", ""):
                        is_expired = True
            except Exception:
                pass

        if is_expired:
            logger.warning("[AUTH] Обнаружен сброс сессии. Выполняется повторный вход...")
            self.login()
            logger.info("[HTTP] >> Повторная отправка запроса...")
            resp = self.session.request(method, url, **kwargs)

        # 2. Запуск транспортного стража (404, WAF, HTML ловушки)
        guard_http_response(resp, url=url, method=method)

        return resp

    def close(self) -> None:
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()