"""Стражи сетевой целостности, защиты от WAF и дрифта схемы данных."""
import logging
from typing import Any, Sequence
import httpx
from dikidi.core.exceptions import (
    DikidiAPIError,
    DikidiAuthError,
    DikidiEndpointNotFoundError,
    DikidiRequestError,
    DikidiSchemaChangedError,
    DikidiWAFBlockedError,
)

logger = logging.getLogger("DikidiGuards")

# Характерные маркеры защиты от ботов / Cloudflare
WAF_MARKERS = (
    "cf-ray",
    "cloudflare",
    "challenge-platform",
    "cf-turnstile",
    "ddos-guard",
    "captcha",
    "just a moment...",
    "attention required! | cloudflare",
)


def guard_http_response(resp: httpx.Response, url: str = "", method: str = "") -> None:
    """Транспортный страж: проверяет статус-код, маркеры WAF и ловушки HTML."""
    target_url = url or str(resp.url)
    target_method = method or resp.request.method if resp.request else "GET"

    # 1. Отлов смены маршрута (404 / 405)
    if resp.status_code in (404, 405):
        raise DikidiEndpointNotFoundError(
            method=target_method,
            url=target_url,
            status_code=resp.status_code,
            response_text=resp.text,
        )

    # 2. Проверка на WAF / Cloudflare
    text_lower = resp.text.lower()
    for marker in WAF_MARKERS:
        if marker in text_lower or marker in str(resp.headers).lower():
            if resp.status_code in (403, 429, 503) or "cloudflare" in text_lower:
                raise DikidiWAFBlockedError(marker, target_url, resp.status_code)

    # 3. Проверка AJAX на HTML-ловушки (сброс сессии на страницу логина)
    content_type = resp.headers.get("content-type", "").lower()
    if "ajax" in target_url and "text/html" in content_type:
        if "<title>авторизация" in text_lower or "/auth/" in text_lower:
            raise DikidiAuthError(f"Сессия сброшена на HTML-страницу логина при запросе к {target_url}")
        if resp.status_code >= 500:
            raise DikidiRequestError(f"Сервер DIKIDI вернул HTML-ошибку {resp.status_code} на {target_url}")


def guard_json_envelope(
    data: Any,
    expected_any: Sequence[str],
    context: str,
) -> dict[str, Any]:
    """Схематический страж: защищает от тихих пустых списков при изменении JSON."""
    if not isinstance(data, dict):
        raise DikidiSchemaChangedError(
            context=context,
            expected_keys=expected_any,
            received_keys=[type(data).__name__],
            sample_payload=str(data)[:250],
        )

    # Проверка бэкенд-ошибки {error: 1, message: "..."}
    if data.get("error") == 1:
        err_msg = data.get("message") or data.get("error_text") or "Неизвестная ошибка DIKIDI API"
        raise DikidiAPIError(f"DIKIDI API [{context}]: {err_msg}")

    # Проверка наличия хотя бы одного якорного ключа
    has_anchor = any(k in data for k in expected_any)
    if not has_anchor:
        raise DikidiSchemaChangedError(
            context=context,
            expected_keys=expected_any,
            received_keys=list(data.keys()),
            sample_payload=str(data)[:300],
        )

    return data


def guard_html_anchor(html_str: str, required_markers_any: Sequence[str], context: str) -> None:
    """HTML-страж: проверяет, что скрапируемый фрагмент содержит ключевые элементы."""
    if not html_str or not html_str.strip():
        raise DikidiSchemaChangedError(
            context=context,
            expected_keys=required_markers_any,
            received_keys=["<empty_html>"],
            sample_payload="",
        )

    html_lower = html_str.lower()
    has_marker = any(m.lower() in html_lower for m in required_markers_any)
    if not has_marker:
        raise DikidiSchemaChangedError(
            context=context,
            expected_keys=required_markers_any,
            received_keys=["<markers_not_found>"],
            sample_payload=html_str[:300],
        )