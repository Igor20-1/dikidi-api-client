import re
from typing import Any
from bs4 import BeautifulSoup
from dikidi.clients.schemas import Client, ClientFilterInfo


def extract_html_from_response(data: dict[str, Any]) -> str:
    """Извлекает сырой HTML из любого типа AJAX-ответа DIKIDI."""
    if not isinstance(data, dict):
        return ""
    if "html" in data and isinstance(data["html"], str):
        return data["html"]
    if "script" in data and isinstance(data["script"], list):
        for item in data["script"]:
            if isinstance(item, dict) and "html" in item:
                return item["html"]
    return ""


def parse_client_form_data(html_str: str) -> dict[str, str]:
    """Извлекает существующие значения полей клиента из HTML модального окна настроек."""
    soup = BeautifulSoup(html_str, "html.parser")
    data: dict[str, str] = {
        "is_for_journal": "1",
        "name": "",
        "surname": "",
        "birthday": "",
        "number": "",
        "email": "",
        "sex": "0",
        "discount": "0",
        "card": "",
        "source_id": "0",
        "comment": "",
        "blacklist_comment": "",
    }

    # Текстовые поля и скрытые инпуты
    for inp in soup.select("input[name]"):
        n = inp.get("name", "").strip()
        val = inp.get("value", "") or ""
        if n in data:
            data[n] = val
        elif n == "phone":
            data["number"] = re.sub(r"\D", "", val)

    # Выпадающие списки (sex, source_id)
    for sel in soup.select("select[name]"):
        n = sel.get("name", "").strip()
        if n in data:
            opt = sel.select_one("option[selected]") or sel.select_one("option")
            if opt:
                data[n] = opt.get("value", "") or ""

    # Текстовые области (comment, blacklist_comment)
    for ta in soup.select("textarea[name]"):
        n = ta.get("name", "").strip()
        if n in data:
            data[n] = ta.get_text().strip()

    if data.get("number"):
        data["number"] = re.sub(r"\D", "", data["number"])

    return data


def parse_clients_html(html_str: str) -> list[Client]:
    """Парсит строки клиентов из переданного HTML-фрагмента."""
    soup = BeautifulSoup(html_str, "html.parser")
    clients = []

    for tr in soup.select("tr[id^='item-']"):
        client_id = tr["id"].replace("item-", "").strip()

        name_el = tr.select_one(".line-name a")
        name = name_el.get_text(strip=True) if name_el else "Без имени"

        phone_el = tr.select_one(".line-phone")
        phone = phone_el.get_text(strip=True) if phone_el else ""

        avatar_el = tr.select_one(".clients_icon")
        avatar_url = None
        if avatar_el and "url(" in avatar_el.get("style", ""):
            match = re.search(r"url\((.*?)\)", avatar_el["style"])
            if match:
                avatar_url = match.group(1).strip("'\"")

        visits_el = tr.select_one(".appointments .count")
        visits = int(visits_el.get_text(strip=True)) if visits_el and visits_el.get_text(strip=True).isdigit() else 0

        last_visit_el = tr.select_one(".lastvizit")
        last_visit = last_visit_el.get_text(strip=True) if last_visit_el else None
        if last_visit == "-":
            last_visit = None

        def _parse_num(selector: str) -> float:
            el = tr.select_one(selector)
            if not el:
                return 0.0
            raw = el.get_text(strip=True).replace(" ", "").replace(",", ".")
            try:
                return float(raw)
            except ValueError:
                return 0.0

        discount = _parse_num(".discount")
        avg_check = _parse_num(".middlecheck")
        spent = _parse_num(".spent")

        groups = []
        for g_el in tr.select(".groups .group-link"):
            tag = g_el.find("a", class_="remove-group-link")
            if tag:
                tag.decompose()
            groups.append(g_el.get_text(strip=True))

        comment_el = tr.select_one(".tooltip-comment")
        comment = comment_el.get("data-original-title") if comment_el else None

        tr_classes = tr.get("class", [])
        is_blocked = "blocked" in tr_classes
        if not is_blocked:
            b_badge = tr.select_one(".line-name .blocked, .client-status .blocked")
            if b_badge and "hide" not in b_badge.get("class", []):
                is_blocked = True

        is_deleted = "deleted" in tr_classes
        if not is_deleted:
            d_badge = tr.select_one(".line-name .deleted, .client-status .deleted")
            if d_badge and "hide" not in d_badge.get("class", []):
                is_deleted = True

        clients.append(Client(
            id=client_id,
            name=name,
            phone=phone,
            visits_count=visits,
            last_visit=last_visit,
            discount=discount,
            avg_check=avg_check,
            spent_total=spent,
            groups=groups,
            comment=comment,
            is_blocked=is_blocked,
            is_deleted=is_deleted,
            avatar_url=avatar_url,
        ))

    return clients


def parse_clients_filter_page(filter_json: dict[str, Any]) -> ClientFilterInfo:
    html = extract_html_from_response(filter_json)
    soup = BeautifulSoup(html, "html.parser")

    count_el = soup.select_one(".count-all, .count-items")
    total_count = int(count_el.get_text(strip=True)) if count_el and count_el.get_text(strip=True).isdigit() else 0

    groups_dict = {}
    for opt in soup.select("select[name='check[clients_groups][]'] option"):
        val = opt.get("value", "").strip()
        if val and val != "0":
            name = BeautifulSoup(opt.get("data-content", opt.text), "html.parser").get_text(strip=True)
            groups_dict[val] = name

    masters_dict = {}
    for opt in soup.select("select[name='check[masters][]'] option"):
        val = opt.get("value", "").strip()
        if val and val != "0":
            masters_dict[val] = opt.text.strip()

    sources_dict = {}
    for opt in soup.select("select[name='check[sources][]'] option"):
        val = opt.get("value", "").strip()
        if val and val != "0":
            sources_dict[val] = opt.text.strip()

    clients = parse_clients_html(html)

    return ClientFilterInfo(
        total_count=total_count,
        clients=clients,
        available_groups=groups_dict,
        available_masters=masters_dict,
        available_sources=sources_dict,
    )