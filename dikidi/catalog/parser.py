from typing import Any
from dikidi.catalog.schemas import CatalogDump, Master, Service
from dikidi.core.guards import guard_json_envelope


def parse_masters(catalog_json: dict[str, Any]) -> list[Master]:
    """Извлекает список мастеров и их должности из ответа masters.info."""
    guard_json_envelope(catalog_json, expected_any=["masters", "master"], context="Каталог: мастера")
    masters_list: list[Master] = []
    masters_data = catalog_json.get("masters", {}).get("info", {}).get("data", {})

    if not isinstance(masters_data, dict):
        return masters_list

    for m_id, m in masters_data.items():
        title = m.get("title", "").strip()
        masters_list.append(Master(
            id=str(m_id),
            name=m.get("name", title),
            post=m.get("post"),
            is_master=str(m.get("is_master", "1")) == "1",
            group_id=str(m.get("group_id")) if m.get("group_id") else None,
            avatar_url=m.get("image"),
        ))
    return masters_list


def parse_services(catalog_json: dict[str, Any]) -> list[Service]:
    """Рекурсивно обходит структуру masters.services и извлекает все услуги."""
    guard_json_envelope(catalog_json, expected_any=["masters", "master"], context="Каталог: услуги")
    services_list: list[Service] = []
    seen_ids = set()

    def _walk(node: Any, current_cat_id: str | None = None, current_cat_name: str | None = None):
        if isinstance(node, dict):
            has_price_or_duration = any(k in node for k in ("cost", "price", "duration", "time"))
            if "id" in node and has_price_or_duration:
                s_id = str(node.get("id"))
                name = node.get("name") or node.get("title")
                if s_id and name and s_id not in seen_ids:
                    seen_ids.add(s_id)
                    raw_cost = str(node.get("cost", node.get("price", 0))).replace(" ", "").replace(",", ".")
                    try:
                        cost = float(raw_cost)
                    except (ValueError, TypeError):
                        cost = 0.0

                    try:
                        duration = int(node.get("duration", node.get("time", 0)) or 0)
                    except (ValueError, TypeError):
                        duration = 0

                    services_list.append(Service(
                        id=s_id,
                        name=name.strip(),
                        cost=cost,
                        duration=duration,
                        category_id=str(node.get("category_id", current_cat_id or "")),
                        category_name=current_cat_name,
                    ))

            node_type = str(node.get("type", "")).lower()
            cat_id = str(node.get("id")) if "category" in node_type else current_cat_id
            cat_name = node.get("name") if "category" in node_type else current_cat_name

            for v in node.values():
                _walk(v, cat_id, cat_name)
        elif isinstance(node, list):
            for item in node:
                _walk(item, current_cat_id, current_cat_name)

    raw_services = catalog_json.get("masters", {}).get("services", {})
    _walk(raw_services)
    return services_list


def parse_catalog_dump(catalog_json: dict[str, Any]) -> CatalogDump:
    return CatalogDump(
        masters=parse_masters(catalog_json),
        services=parse_services(catalog_json),
    )