import logging
import re
import time
import httpx
from dikidi.core.config import AUTH_URL, BASE_URL, NET_URL, CRITICAL_COOKIES
from dikidi.core.exceptions import DikidiAuthError

logger = logging.getLogger("DikidiAuth")


class AuthFlow:
    """Процедура полной аутентификации в DIKIDI Business."""

    @staticmethod
    def extract_telegram_csrf(client: httpx.Client) -> str:
        logger.info("[AUTH] Шаг 0: Получение начального CSRF-токена с %s/ru/ ...", BASE_URL)
        resp = client.get(f"{BASE_URL}/ru/")
        resp.raise_for_status()

        match = re.search(r'telegram_csrf["\']?\s*[:=]\s*["\']([a-f0-9]{32}:\d+\.\d+)["\']', resp.text)
        if match:
            return match.group(1)

        match_fallback = re.search(r'([a-f0-9]{32}:\d{10}\.\d+)', resp.text)
        if match_fallback:
            return match_fallback.group(1)

        raise DikidiAuthError("Не удалось извлечь токен telegram_csrf со страницы")

    @staticmethod
    def sync_cookies_to_net(client: httpx.Client) -> None:
        """Копирует критические куки авторизации на .dikidi.net."""
        for c in list(client.cookies.jar):
            if c.name in CRITICAL_COOKIES:
                client.cookies.set(
                    name=c.name,
                    value=c.value,
                    domain=".dikidi.net",
                    path=c.path or "/",
                )

    @classmethod
    def login(cls, client: httpx.Client, phone: str, password: str, company_id: str) -> str:
        """Выполняет полный цикл аутентификации и возвращает user_id."""
        logger.info("[AUTH] === СТАРТ АВТОРИЗАЦИИ ДЛЯ НОМЕРА: %s ===", phone)
        client.cookies.clear()

        telegram_csrf = cls.extract_telegram_csrf(client)
        logger.info("[AUTH] Токен telegram_csrf: %s", telegram_csrf)

        auth_headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/ru/",
        }

        # Шаг 1: Проверка номера
        logger.info("[AUTH] Шаг 1: Проверка номера телефона...")
        resp_check = client.post(
            f"{AUTH_URL}/ajax/check/auth/",
            data={"telegram_csrf": telegram_csrf, "number": phone},
            headers=auth_headers,
        )
        resp_check.raise_for_status()

        secondary_csrf = telegram_csrf
        try:
            check_json = resp_check.json()
            if isinstance(check_json, dict) and "csrf" in check_json:
                secondary_csrf = check_json["csrf"]
        except Exception:
            pass

        time.sleep(0.3)

        # Шаг 2: Отправка пароля
        logger.info("[AUTH] Шаг 2: Проверка пароля на шлюзе...")
        resp_auth = client.post(
            f"{AUTH_URL}/ajax/user/auth/",
            data={
                "telegram_csrf": telegram_csrf,
                "number": phone,
                "csrf": secondary_csrf,
                "password": password,
                "pdAgreement": "1",
            },
            headers=auth_headers,
        )
        resp_auth.raise_for_status()
        auth_data = resp_auth.json()

        if not ("callback" in auth_data and any("sw.auth.complete" in cb for cb in auth_data["callback"])):
            raise DikidiAuthError(f"Сервер отказал в авторизации: {auth_data}")

        user_id = ""
        match_uid = re.search(r"sw\.auth\.complete\('([a-f0-9]+)'\)", auth_data["callback"][0])
        if match_uid:
            user_id = match_uid.group(1)
        logger.info("[AUTH] Авторизация успешна! User ID: %s", user_id)

        # Шаг 3: Handshake с CRM на dikidi.net
        cls.sync_cookies_to_net(client)
        logger.info("[AUTH] Шаг 3: Инициализация CRM-сессии на %s для компании %s ...", NET_URL, company_id)

        init_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
            "Referer": f"{BASE_URL}/ru/",
        }
        resp_init = client.get(
            f"{NET_URL}/ru/owner/journal/?company={company_id}",
            headers=init_headers,
            follow_redirects=True,
        )
        logger.info("[AUTH] Шаг 3 завершен! Статус: %d", resp_init.status_code)
        logger.info("[AUTH] === АВТОРИЗАЦИЯ И ИНИЦИАЛИЗАЦИЯ УСПЕШНО ЗАВЕРШЕНЫ ===")
        return user_id