import json
import logging
import time
from pathlib import Path
import httpx

logger = logging.getLogger("DikidiTokenStorage")


def resolve_session_path(file_path: str | Path = "session_cookies.json") -> Path:
    """Умный резолвер: якорит относительный путь к корню проекта.

    Если передан относительный путь, ищет корень проекта (по наличию
    папки 'dikidi' или файла '.env'), чтобы сессия не дублировалась в 'tests/'.
    """
    p = Path(file_path)
    if p.is_absolute():
        return p

    # Проверяем текущую папку и всех родителей вверх
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".env").exists() or (parent / "dikidi").is_dir():
            return parent / p

    return current / p


class TokenStorage:
    """Хранилище cookies и метаданных сессии в JSON-файле."""

    def __init__(self, file_path: str | Path = "session_cookies.json"):
        self.file_path = resolve_session_path(file_path)

    def save(self, cookies: httpx.Cookies, user_id: str | None = None) -> None:
        cookies_list = [
            {
                "name": c.name,
                "value": c.value,
                "domain": c.domain,
                "path": c.path,
                "secure": c.secure,
                "expires": c.expires,
            }
            for c in cookies.jar
        ]
        data = {
            "user_id": user_id,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "cookies": cookies_list,
        }
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("[COOKIE] Сохранено %d кук в: %s", len(cookies_list), self.file_path)

    def load(self, cookies: httpx.Cookies) -> tuple[bool, str | None]:
        if not self.file_path.exists():
            logger.info("[COOKIE] Файл сохраненной сессии (%s) не найден.", self.file_path)
            return False, None

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            user_id = data.get("user_id")
            cookies_list = data.get("cookies", [])

            for item in cookies_list:
                cookies.set(
                    name=item["name"],
                    value=item["value"],
                    domain=item.get("domain", ".dikidi.net"),
                    path=item.get("path", "/"),
                )

            logger.info(
                "[COOKIE] Загружено %d кук из кэша (User ID: %s, дата: %s)",
                len(cookies_list),
                user_id,
                data.get("saved_at", "н/д"),
            )
            return True, user_id
        except Exception as e:
            logger.warning("[COOKIE] Ошибка при чтении файла сессии: %s", e)
            return False, None