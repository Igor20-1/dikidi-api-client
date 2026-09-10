from typing import Any
from dikidi.appointments.schemas import MasterShift, Record, ReservationResult
from dikidi.core.guards import guard_json_envelope
from dikidi.core.exceptions import DikidiAPIError, DikidiSchemaChangedError

STATUS_MAP = {
    "0": "Новая / Ожидание",
    "1": "Подтверждена",
    "2": "Клиент пришел",
    "3": "Не пришел",
    "4": "Отменена",
    "5": "Удалена",
}


def parse_records(journal_json: dict[str, Any]) -> list[Record]:
    """Извлекает реальные записи из структуры records['data'][master_id][date][record_id]."""
    guard_json_envelope(journal_json, expected_any=["masters", "master"], context="Журнал записей (masters.records)")

    records_list: list[Record] = []
    masters_obj = journal_json.get("masters") or journal_json.get("master") or {}

    if "records" not in masters_obj:
        raise DikidiSchemaChangedError(
            context="Ключ 'records' в masters",
            expected_keys=["records"],
            received_keys=list(masters_obj.keys()),
            sample_payload=str(masters_obj)[:250],
        )

    records_data = masters_obj.get("records", {}).get("data", {})
    if not isinstance(records_data, dict):
        return records_list

    for master_id, dates_dict in records_data.items():
        if not isinstance(dates_dict, dict):
            continue

        for date_str, appts_dict in dates_dict.items():
            if not isinstance(appts_dict, dict):
                continue

            for rec_id, r in appts_dict.items():
                if not isinstance(r, dict) or "begin" not in r:
                    continue

                info = r.get("info", {}) if isinstance(r.get("info"), dict) else {}
                client_obj = info.get("client") if isinstance(info.get("client"), dict) else {}

                client_name = (
                        info.get("client_name")
                        or client_obj.get("name")
                        or info.get("username")
                        or r.get("client_name")
                )
                client_phone = (
                        info.get("client_phone")
                        or client_obj.get("phone")
                        or info.get("phone")
                        or r.get("client_phone")
                )
                client_id = str(info.get("client_id") or client_obj.get("id") or "") or None

                comment = (info.get("comment") or r.get("comment") or info.get("title") or r.get(
                    "title") or "").strip() or None

                services_list = []
                total_cost = 0.0

                raw_services = info.get("services") or r.get("services") or []
                if isinstance(raw_services, list):
                    for s in raw_services:
                        if isinstance(s, dict):
                            s_title = s.get("title") or s.get("name")
                            if s_title:
                                services_list.append(s_title.strip())

                            s_cost_raw = (
                                str(s.get("cost", s.get("price", 0)))
                                .replace(" ", "")
                                .replace(",", ".")
                            )
                            try:
                                total_cost += float(s_cost_raw)
                            except (ValueError, TypeError):
                                pass

                if not services_list and info.get("services_title"):
                    services_list = [t.strip() for t in info["services_title"].split(",") if t.strip()]

                # Распознавание служебных блокировок (дежурства, личное время, перерывы)
                is_anonym = str(info.get("is_anonym") or r.get("is_anonym") or "0") == "1"
                is_block = (not client_name and not services_list) or str(r.get("type", "")).lower() in (
                "break", "personal", "block")

                if is_block:
                    if not client_name:
                        if is_anonym:
                            client_name = "Анонимный клиент"
                        elif comment:
                            client_name = f"[{comment}]"
                        else:
                            client_name = "[Служебное время]"

                    if not services_list:
                        services_list = [comment or "Служебная блокировка"]

                status_id = str(info.get("status_id") or r.get("status_id") or "")
                came_id = str(info.get("client_came_id") or "")

                if came_id == "1":
                    status = "Клиент пришел"
                elif came_id == "2":
                    status = "Не пришел"
                else:
                    status = STATUS_MAP.get(status_id, f"Статус #{status_id}" if status_id else "Новая")

                raw_begin = str(r.get("begin", "")).strip()
                t_start = raw_begin.split(" ")[-1] if " " in raw_begin else raw_begin

                raw_end = str(r.get("end", "")).strip()
                t_end = raw_end.split(" ")[-1] if " " in raw_end else raw_end

                duration_sec = int(r.get("duration", 0) or 0)
                duration_min = duration_sec // 60 if duration_sec > 0 else 0

                records_list.append(
                    Record(
                        id=str(r.get("id", rec_id)),
                        master_id=str(r.get("item_id") or master_id),
                        date=str(r.get("date", date_str)),
                        time_start=t_start,
                        time_end=t_end,
                        duration_minutes=duration_min,
                        client_name=client_name,
                        client_phone=client_phone,
                        client_id=client_id,
                        cost=total_cost,
                        services=services_list,
                        status=status,
                        comment=comment,
                        is_block=is_block,
                    )
                )

    return records_list


def _extract_shift_item(m_id: str, d_str: str, shift: dict[str, Any]) -> MasterShift:
    """Вспомогательная функция формирования MasterShift из словаря смены."""
    raw_from = str(shift.get("work_from") or shift.get("begin") or "00:00:00").strip()
    work_from = raw_from.split(" ")[-1] if " " in raw_from else raw_from

    raw_to = str(shift.get("work_to") or shift.get("end") or "00:00:00").strip()
    work_to = raw_to.split(" ")[-1] if " " in raw_to else raw_to

    raw_b_from = str(shift.get("break_from", "00:00:00") or "00:00:00").strip()
    break_from = raw_b_from.split(" ")[-1] if " " in raw_b_from else raw_b_from

    raw_b_to = str(shift.get("break_to", "00:00:00") or "00:00:00").strip()
    break_to = raw_b_to.split(" ")[-1] if " " in raw_b_to else raw_b_to

    return MasterShift(
        master_id=str(shift.get("item_id") or m_id),
        date=str(shift.get("date") or d_str),
        work_from=work_from,
        work_to=work_to,
        break_from=break_from,
        break_to=break_to,
        appointments_count=int(shift.get("appointments_count", 0) or 0),
    )


def parse_schedules(journal_json: dict[str, Any]) -> list[MasterShift]:
    """Универсальный парсер графика смен (поддерживает и masters.schedules, и master.schedules)."""
    guard_json_envelope(journal_json, expected_any=["masters", "master"], context="График смен (masters.schedules)")

    shifts_list: list[MasterShift] = []
    for root_key in ("masters", "master"):
        root_data = journal_json.get(root_key)
        if not isinstance(root_data, dict):
            continue

        sched = root_data.get("schedules")
        if not isinstance(sched, dict):
            continue

        if "data" in sched and isinstance(sched["data"], dict):
            for m_id, dates_dict in sched["data"].items():
                if isinstance(dates_dict, dict):
                    for d_str, shift in dates_dict.items():
                        if isinstance(shift, dict):
                            shifts_list.append(_extract_shift_item(str(m_id), str(d_str), shift))

        for m_id, val in sched.items():
            if m_id == "data" or not isinstance(val, dict):
                continue
            dates_dict = val.get("data") if isinstance(val.get("data"), dict) else val
            if isinstance(dates_dict, dict):
                for d_str, shift in dates_dict.items():
                    if isinstance(shift, dict) and any(k in shift for k in ("work_from", "work_to", "begin", "end")):
                        shifts_list.append(_extract_shift_item(str(m_id), str(d_str), shift))

    return shifts_list


def parse_reservation_response(resp_json: dict[str, Any], unique_key: str) -> ReservationResult:
    guard_json_envelope(resp_json, expected_any=["record_id", "id", "data"], context="Холдирование слота")

    record_id = None
    if "record_id" in resp_json:
        record_id = str(resp_json["record_id"])
    elif "id" in resp_json:
        record_id = str(resp_json["id"])
    elif "data" in resp_json and isinstance(resp_json["data"], dict):
        record_id = str(resp_json["data"].get("record_id") or resp_json["data"].get("id"))

    if not record_id:
        raise DikidiAPIError(f"Не удалось извлечь record_id из ответа: {resp_json}")

    return ReservationResult(
        record_id=record_id,
        unique_key=unique_key,
        raw_response=resp_json,
    )