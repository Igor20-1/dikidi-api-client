"""Иерархия исключений DIKIDI SDK."""
from typing import Any, Sequence


class DikidiError(Exception):
    """Базовое исключение SDK DIKIDI."""
    pass


class DikidiAuthError(DikidiError):
    """Ошибка аутентификации (неверный пароль, сброс сессии, редирект на логин)."""
    pass


class DikidiRequestError(DikidiError):
    """Ошибка сетевого взаимодействия или невалидный HTTP-статус."""
    pass


class DikidiAPIError(DikidiError):
    """Ошибка, возвращенная бэкендом DIKIDI в теле JSON (error: 1)."""
    pass


class DikidiEndpointNotFoundError(DikidiRequestError):
    """Шлюз или эндпоинт DIKIDI не найден (HTTP 404 / 405).

    Сигнал о том, что URL веб-шлюза изменился на стороне DIKIDI.
    """

    def __init__(self, method: str, url: str, status_code: int, response_text: str = ""):
        self.method = method
        self.url = url
        self.status_code = status_code
        self.response_preview = response_text[:250].strip()
        super().__init__(
            f"[API DRIFT] Эндпоинт {method} {url} вернул HTTP {status_code}! "
            f"Возможно, DIKIDI изменил маршрут. Ответ сервера: {self.response_preview}"
        )


class DikidiWAFBlockedError(DikidiRequestError):
    """Запрос перехвачен WAF, Cloudflare, капчей или DDoS-защитой."""

    def __init__(self, indicator: str, url: str, status_code: int):
        self.indicator = indicator
        self.url = url
        self.status_code = status_code
        super().__init__(
            f"[WAF/BLOCK] Обнаружена блокировка запроса к {url} (HTTP {status_code})! "
            f"Сработавший триггер: '{indicator}'. Требуется проверка IP или заголовков."
        )


class DikidiSchemaChangedError(DikidiError):
    """Структура JSON или HTML ответа DIKIDI кардинально изменилась.

    Защищает от «тихого отказа» (Silent Failure), когда парсер возвращает
    пустой список [] из-за переименования полей на бэкенде.
    """

    def __init__(
        self,
        context: str,
        expected_keys: Sequence[str],
        received_keys: Sequence[str],
        sample_payload: str = "",
    ):
        self.context = context
        self.expected_keys = list(expected_keys)
        self.received_keys = list(received_keys)
        self.sample_payload = sample_payload[:300].strip()
        super().__init__(
            f"[SCHEMA DRIFT] В шлюзе '{context}' изменилась структура данных!\n"
            f"  • Ожидался хотя бы один из ключей: {self.expected_keys}\n"
            f"  • Фактически получены ключи:       {self.received_keys}\n"
            f"  • Фрагмент ответа сервера:         {self.sample_payload}"
        )