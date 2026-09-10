import logging
from typing import Any
from dikidi.core.config import NET_URL
from dikidi.core.transport import DikidiTransport
from dikidi.catalog.schemas import CatalogDump, Master, Service
from dikidi.catalog.parser import parse_catalog_dump, parse_masters, parse_services

logger = logging.getLogger("DikidiCatalogService")


class CatalogService:
    """Сервис управления прайс-листом и мастерами DIKIDI."""

    def __init__(self, transport: DikidiTransport):
        self.transport = transport
        self.company_id = transport.config.company_id

    def get_catalog(self) -> CatalogDump:
        """Получает полный каталог: всех мастеров и всё дерево услуг."""
        url = f"{NET_URL}/ru/owner/ajax/journal/api/?company={self.company_id}"
        headers = self.transport.get_ajax_headers(f"/ru/owner/journal/?company={self.company_id}")
        data = {
            "request[get][]": ["company.accesses", "masters.info", "masters.services"],
            "request[options][company][accesses][]": self.company_id,
        }
        resp = self.transport.request("POST", url, headers=headers, data=data)
        resp.raise_for_status()
        return parse_catalog_dump(resp.json())

    def get_masters(self) -> list[Master]:
        """Возвращает список сотрудников/мастеров студии."""
        catalog = self.get_catalog()
        return catalog.masters

    def get_services(self) -> list[Service]:
        """Возвращает плоский список всех активных услуг."""
        catalog = self.get_catalog()
        return catalog.services

    def get_available_masters_for_service(
        self,
        service_id: str | int,
        date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Запрашивает мастеров под услугу и гарантированно возвращает list[dict]."""
        url = f"{NET_URL}/ajax/newrecord/get_masters/"
        params: dict[str, Any] = {
            "company_id": self.company_id,
            "services_id[]": str(service_id),
            "action_source_id": "3",
            "is_show_all_times": "false",
            "is-from-journal": "1",
        }
        if date:
            params["date"] = date

        headers = self.transport.get_ajax_headers(f"/ru/owner/clients/?company={self.company_id}")
        resp = self.transport.request("GET", url, headers=headers, params=params)
        resp.raise_for_status()

        result = resp.json()
        # Приводим к списку объектов, независимо от структуры ответа
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            inner = result.get("data") or result.get("masters")
            if isinstance(inner, dict):
                return list(inner.values())
            if isinstance(inner, list):
                return inner
            return list(result.values())
        return []