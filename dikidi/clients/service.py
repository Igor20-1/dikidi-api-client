import asyncio
import logging
from typing import Any
import httpx
from dikidi.core.config import NET_URL
from dikidi.core.exceptions import DikidiAPIError
from dikidi.core.transport import DikidiTransport
from dikidi.clients.schemas import Client, ClientCreate, ClientFilterInfo, ClientUpdate
from dikidi.clients.parser import (
    extract_html_from_response,
    parse_client_form_data,
    parse_clients_html,
    parse_clients_filter_page,
)

logger = logging.getLogger("DikidiClientService")


class ClientService:
    """Сервис управления базой клиентов DIKIDI (CRUD, поиск, выгрузка)."""

    def __init__(self, transport: DikidiTransport):
        self.transport = transport
        self.company_id = transport.config.company_id

    def get_filter_info(self) -> ClientFilterInfo:
        """Получает счетчики, доступные категории, источники и первые 20 клиентов."""
        url = f"{NET_URL}/ru/owner/ajax/clients/filter/?company={self.company_id}"
        headers = self.transport.get_ajax_headers(f"/ru/owner/clients/?company={self.company_id}")
        resp = self.transport.request("GET", url, headers=headers)
        resp.raise_for_status()
        return parse_clients_filter_page(resp.json())

    def get_page(self, offset: int = 0, limit: int = 50, query: str = "") -> list[Client]:
        """Загружает порцию клиентов по смещению и фильтру."""
        url = f"{NET_URL}/ru/owner/ajax/clients/filter/?company={self.company_id}"
        headers = self.transport.get_ajax_headers(f"/ru/owner/clients/?company={self.company_id}")
        data = {
            "company": self.company_id,
            "limit": str(limit),
            "offset": str(offset),
            "filter": "username",
            "order": "asc",
            "more": "1",
            "query": query,
        }
        resp = self.transport.request("POST", url, headers=headers, data=data)
        resp.raise_for_status()
        html = extract_html_from_response(resp.json())
        return parse_clients_html(html)

    def search(self, query: str, limit: int = 20) -> list[Client]:
        """Ищет клиентов по имени или номеру телефона."""
        return self.get_page(offset=0, limit=limit, query=query)

    def create(self, client_data: ClientCreate) -> dict[str, Any]:
        """Создает нового клиента в CRM через шлюз clients/save/."""
        url = f"{NET_URL}/ru/owner/ajax/clients/save/?company={self.company_id}"
        headers = self.transport.get_ajax_headers(f"/ru/owner/clients/?company={self.company_id}")

        form_data = client_data.to_form_data()
        resp = self.transport.request("POST", url, headers=headers, data=form_data)
        resp.raise_for_status()

        result = resp.json()
        if isinstance(result, dict) and result.get("error") == 1:
            raise DikidiAPIError(f"Ошибка при создании клиента: {result.get('message')}")

        logger.info("[CLIENT] Клиент '%s' успешно сохранен! Ответ: %s", client_data.name, result)
        return result

    def get_card(self, client_id: str | int) -> dict[str, Any]:
        """Загружает карточку настроек клиента (шлюз clients/settings/{client_id}/)."""
        cid = str(client_id).strip()
        url = f"{NET_URL}/ru/owner/ajax/clients/settings/{cid}/?company={self.company_id}"
        headers = self.transport.get_ajax_headers(f"/ru/owner/clients/?company={self.company_id}")
        resp = self.transport.request("GET", url, headers=headers)
        resp.raise_for_status()
        return resp.json()

    def update(
        self,
        client_id: str | int,
        client_data: ClientUpdate | ClientCreate | None = None,
        *,
        auto_fetch_current: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Безопасное обновление клиента с авто-сохранением непереданных полей (Email, ДР, скидка и т.д.)."""
        cid = str(client_id).strip()
        url = f"{NET_URL}/ru/owner/ajax/clients/save/{cid}/?company={self.company_id}"
        headers = self.transport.get_ajax_headers(f"/ru/owner/clients/?company={self.company_id}")

        form_data: dict[str, str] = {}
        if auto_fetch_current:
            try:
                card_resp = self.get_card(cid)
                html = extract_html_from_response(card_resp)
                if html:
                    form_data = parse_client_form_data(html)
            except Exception as e:
                logger.warning("[CLIENT] Не удалось предзагрузить карточку клиента ID %s: %s", cid, e)

        # 1. Если передан ClientUpdate
        if isinstance(client_data, ClientUpdate):
            form_data = client_data.apply_to_form_data(form_data)
        # 2. Если передан ClientCreate
        elif isinstance(client_data, ClientCreate):
            create_data = client_data.to_form_data()
            create_data["is_for_journal"] = "1"
            if auto_fetch_current:
                for k, v in create_data.items():
                    if v not in ("", "0", "0.0"):
                        form_data[k] = v
            else:
                form_data = create_data
        elif client_data is None and not kwargs:
            raise ValueError("Не переданы данные для обновления клиента (client_data или kwargs).")

        # 3. Наложение точечных kwargs (name, comment, discount, phone и т.д.)
        if kwargs:
            upd_kwargs = ClientUpdate(
                name=kwargs.get("name"),
                phone=kwargs.get("phone") or kwargs.get("number"),
                surname=kwargs.get("surname"),
                email=kwargs.get("email"),
                sex=kwargs.get("sex"),
                birthday=kwargs.get("birthday"),
                discount=kwargs.get("discount"),
                card=kwargs.get("card"),
                source_id=kwargs.get("source_id"),
                comment=kwargs.get("comment"),
                blacklist_comment=kwargs.get("blacklist_comment"),
            )
            form_data = upd_kwargs.apply_to_form_data(form_data)

        logger.info("[CLIENT] Безопасное сохранение клиента ID %s (%s)...", cid, form_data.get("name"))
        resp = self.transport.request("POST", url, headers=headers, data=form_data)
        resp.raise_for_status()

        result = resp.json()
        if isinstance(result, dict) and result.get("error") == 1:
            raise DikidiAPIError(f"Ошибка при обновлении клиента: {result.get('message')}")

        logger.info("[CLIENT] Клиент ID %s успешно сохранен! Ответ: %s", cid, result)
        return result

    def get_history(self, client_id: str | int) -> dict[str, Any]:
        """Получает историю визитов и действий по клиенту."""
        cid = str(client_id).strip()
        url = f"{NET_URL}/ru/owner/ajax/clients/settings/{cid}/?company={self.company_id}&tab=history"
        headers = self.transport.get_ajax_headers(f"/ru/owner/clients/?company={self.company_id}")
        resp = self.transport.request("POST", url, headers=headers, data={"tabs": "true"})
        resp.raise_for_status()
        return resp.json()

    async def get_all_async(self, batch_size: int = 50, concurrency: int = 6) -> list[Client]:
        """Параллельная выгрузка всех клиентов компании."""
        filter_info = self.get_filter_info()
        total_count = filter_info.total_count

        all_clients: list[Client] = list(filter_info.clients)
        offsets = list(range(len(filter_info.clients), total_count, batch_size))

        cookies = {c.name: c.value for c in self.transport.session.cookies.jar}
        headers = self.transport.get_ajax_headers(f"/ru/owner/clients/?company={self.company_id}")
        semaphore = asyncio.Semaphore(concurrency)

        async def _fetch_batch(async_cli: httpx.AsyncClient, off: int) -> list[Client]:
            url = f"{NET_URL}/ru/owner/ajax/clients/filter/?company={self.company_id}"
            data = {
                "company": self.company_id,
                "limit": str(batch_size),
                "offset": str(off),
                "filter": "username",
                "order": "asc",
                "more": "1",
            }
            async with semaphore:
                for _ in range(3):
                    try:
                        r = await async_cli.post(url, headers=headers, data=data, timeout=20.0)
                        if r.status_code == 200:
                            h = extract_html_from_response(r.json())
                            return parse_clients_html(h)
                    except Exception:
                        await asyncio.sleep(0.3)
                return []

        async with httpx.AsyncClient(http2=True, cookies=cookies) as async_client:
            tasks = [_fetch_batch(async_client, off) for off in offsets]
            results = await asyncio.gather(*tasks)

        for batch in results:
            all_clients.extend(batch)

        logger.info("[CLIENT] Асинхронно выгружено клиентов: %d из %d", len(all_clients), total_count)
        return all_clients