import logging
import random
from typing import Any
from dikidi.core.config import NET_URL
from dikidi.core.transport import DikidiTransport
from dikidi.core.exceptions import DikidiAPIError
from dikidi.appointments.schemas import (
    AppointmentUpdate,
    BookingRequest,
    DaySlotsReport,
    MasterShift,
    Record,
    ReservationResult,
)
from dikidi.appointments.parser import parse_records, parse_reservation_response, parse_schedules
from dikidi.appointments.slots_engine import FreeSlotsEngine

logger = logging.getLogger("DikidiAppointmentService")


class AppointmentService:
    """Сервис управления журналом записей, онлайн-бронированием и свободными слотами."""

    def __init__(self, transport: DikidiTransport):
        self.transport = transport
        self.company_id = transport.config.company_id
        self._catalog_service = None

    @property
    def _catalog(self):
        if self._catalog_service is None:
            from dikidi.catalog.service import CatalogService
            self._catalog_service = CatalogService(self.transport)
        return self._catalog_service

    def get_records(self, date_from: str, date_to: str) -> list[Record]:
        """Получает журнал записей за указанный период (формат YYYY-MM-DD)."""
        url = f"{NET_URL}/ru/owner/ajax/journal/api/?company={self.company_id}"
        headers = self.transport.get_ajax_headers(f"/ru/owner/journal/?company={self.company_id}")
        data = {
            "request[get][]": ["masters.info", "masters.records", "masters.schedules"],
            "request[options][masters][records][0][date_from]": date_from,
            "request[options][masters][records][0][date_to]": date_to,
            "request[options][masters][schedules][0][date_from]": date_from,
            "request[options][masters][schedules][0][date_to]": date_to,
        }
        resp = self.transport.request("POST", url, headers=headers, data=data)
        resp.raise_for_status()
        return parse_records(resp.json())

    def get_schedules(self, date_from: str, date_to: str) -> list[MasterShift]:
        """Получает график рабочих смен мастеров за период."""
        url = f"{NET_URL}/ru/owner/ajax/journal/api/?company={self.company_id}"
        headers = self.transport.get_ajax_headers(f"/ru/owner/journal/?company={self.company_id}")
        data = {
            "request[get][]": ["masters.schedules"],
            "request[options][masters][schedules][0][date_from]": date_from,
            "request[options][masters][schedules][0][date_to]": date_to,
        }
        resp = self.transport.request("POST", url, headers=headers, data=data)
        resp.raise_for_status()
        return parse_schedules(resp.json())

    def get_slots_report(
        self,
        master_id: str | int,
        date: str,
        service_id: str | int | None = None,
        service_ids: list[str | int] | None = None,
        duration_minutes: int | None = None,
        step_minutes: int = 30,
        allow_past: bool = False,
    ) -> DaySlotsReport:
        """Формирует диагностический отчёт о расписании, занятости и свободных слотах."""
        m_id = str(master_id)
        catalog = self._catalog.get_catalog()
        master_obj = next((m for m in catalog.masters if str(m.id) == m_id), None)
        master_name = master_obj.name if master_obj else f"Мастер #{m_id}"

        target_ids = []
        if service_id:
            target_ids.append(str(service_id))
        if service_ids:
            target_ids.extend([str(sid) for sid in service_ids])

        matched_services = [s for s in catalog.services if s.id in target_ids]
        service_name = ", ".join(s.name for s in matched_services) if matched_services else None

        total_dur = duration_minutes or (sum(s.duration for s in matched_services) if matched_services else 0)
        total_dur = total_dur if total_dur > 0 else step_minutes

        shifts = self.get_schedules(date, date)
        master_shift = next((s for s in shifts if s.master_id == m_id), None)
        records = [r for r in self.get_records(date, date) if r.master_id == m_id and r.date == date]

        free_slots = FreeSlotsEngine.calculate(
            shift=master_shift,
            records=records,
            duration_minutes=total_dur,
            step_minutes=step_minutes,
            date_str=date,
            allow_past=allow_past,
        )

        return DaySlotsReport(
            master_id=m_id,
            master_name=master_name,
            date=date,
            service_id=str(service_id) if service_id else None,
            service_name=service_name,
            duration_minutes=total_dur,
            shift=master_shift,
            busy_records=records,
            free_slots=free_slots,
        )

    def get_free_slots(
        self,
        master_id: str | int,
        date: str,
        service_id: str | int | None = None,
        service_ids: list[str | int] | None = None,
        duration_minutes: int | None = None,
        step_minutes: int = 30,
        allow_past: bool = False,
    ) -> list[str]:
        """Возвращает плоский список доступных окон времени."""
        return self.get_slots_report(
            master_id=master_id,
            date=date,
            service_id=service_id,
            service_ids=service_ids,
            duration_minutes=duration_minutes,
            step_minutes=step_minutes,
            allow_past=allow_past,
        ).free_slots

    def reserve_time(
        self,
        master_id: str | int,
        service_ids: list[str | int],
        time_str: str,
        unique_key: str | None = None,
    ) -> ReservationResult:
        """Фаза 1: Заморозка слота времени мастера (cURL time_reservation)."""
        key = unique_key or str(random.randint(10000000, 99999999))
        url = f"{NET_URL}/ajax/newrecord/time_reservation/"
        params: dict[str, Any] = {
            "company_id": self.company_id,
            "master_id": str(master_id),
            "time": time_str,
            "action_source_id": "3",
            "is-from-journal": "1",
            "unique_key": key,
        }
        services_params = [("services_id[]", str(s_id)) for s_id in service_ids]
        headers = self.transport.get_ajax_headers(f"/ru/owner/clients/?company={self.company_id}")

        resp = self.transport.request("GET", url, headers=headers, params={**params, **dict(services_params)})
        resp.raise_for_status()
        return parse_reservation_response(resp.json(), unique_key=key)

    def save_appointment(
        self,
        record_id: str | int,
        unique_key: str,
        client_name: str,
        client_phone: str,
        client_id: str | int | None = None,
        comment: str = "",
    ) -> dict[str, Any]:
        """Фаза 2: Первичное сохранение создаваемой записи (newrecord_record_save)."""
        url = f"{NET_URL}/owner/ajax/journal/newrecord_record_save/?company={self.company_id}"
        headers = self.transport.get_ajax_headers(f"/ru/owner/clients/?company={self.company_id}")
        data = {
            "client_name": client_name.strip(),
            "client_id": str(client_id or "0"),
            "client_phone": client_phone.strip(),
            "is_anonym": "0",
            "remind[]": "0",
            "comments": comment.strip(),
            "color_label_id": "0",
            "record_id": str(record_id),
            "unique_key": str(unique_key),
        }
        resp = self.transport.request("POST", url, headers=headers, data=data)
        resp.raise_for_status()
        res = resp.json()
        if isinstance(res, dict) and res.get("error") == 1:
            raise DikidiAPIError(f"Ошибка сохранения записи: {res.get('message')}")
        return res

    def update_record(self, update_data: AppointmentUpdate) -> dict[str, Any]:
        """Обновляет существующую запись в журнале (шлюз record_save)."""
        url = f"{NET_URL}/ru/owner/ajax/journal/record_save/?company={self.company_id}"
        headers = self.transport.get_ajax_headers(f"/ru/owner/journal/?company={self.company_id}")
        form_data = update_data.to_form_data(self.company_id)

        logger.info("[BOOKING] Обновление записи ID %s на %s %s...", update_data.appointment_id, update_data.date, update_data.time)
        resp = self.transport.request("POST", url, headers=headers, data=form_data)
        resp.raise_for_status()

        res = resp.json()
        if isinstance(res, dict) and res.get("error") == 1:
            raise DikidiAPIError(f"Ошибка обновления записи: {res.get('message')}")
        logger.info("[BOOKING] Запись ID %s успешно обновлена!", update_data.appointment_id)
        return res

    def _to_update_model(self, record: Record | AppointmentUpdate) -> AppointmentUpdate:
        """Вспомогательный метод приведения Record к редактируемой модели."""
        if isinstance(record, AppointmentUpdate):
            return record
        return AppointmentUpdate(
            appointment_id=record.id,
            master_id=record.master_id,
            date=record.date,
            time=record.time_start,
            client_name=record.client_name or "Клиент",
            client_phone=record.client_phone or "",
            client_id=record.client_id,
            comment=record.comment or "",
        )

    def reschedule(
        self,
        record: Record | AppointmentUpdate,
        new_date: str,
        new_time: str,
        new_master_id: str | int | None = None,
    ) -> dict[str, Any]:
        """Переносит существующую запись на другую дату/время."""
        upd = self._to_update_model(record)
        upd.date = new_date
        upd.time = new_time
        if new_master_id:
            upd.master_id = new_master_id
        return self.update_record(upd)

    def change_status(
        self,
        record: Record | AppointmentUpdate,
        came_id: int | None = None,
        is_accept: int | None = None,
    ) -> dict[str, Any]:
        """Изменяет статус визита клиента: came_id (1: пришел, 2: не пришел), is_accept (1: подтверждена)."""
        upd = self._to_update_model(record)
        if came_id is not None:
            upd.client_came_id = came_id
        if is_accept is not None:
            upd.is_accept = is_accept
        return self.update_record(upd)

    def book(self, request: BookingRequest) -> dict[str, Any]:
        """Сквозная онлайн-запись: холдирует слот и сохраняет запись."""
        res = self.reserve_time(
            master_id=request.master_id,
            service_ids=request.service_ids,
            time_str=request.time_str,
        )
        return self.save_appointment(
            record_id=res.record_id,
            unique_key=res.unique_key,
            client_name=request.client_name,
            client_phone=request.client_phone,
            client_id=request.client_id,
            comment=request.comment,
        )

    def remove(self, appointment_id: str | int) -> dict[str, Any]:
        """Удаляет запись из журнала CRM."""
        url = f"{NET_URL}/ru/owner/ajax/journal/remove/{appointment_id}/?company={self.company_id}"
        headers = self.transport.get_ajax_headers(f"/ru/owner/journal/?company={self.company_id}")
        resp = self.transport.request("GET", url, headers=headers)
        resp.raise_for_status()
        res = resp.json()
        if isinstance(res, dict) and res.get("error") == 1:
            raise DikidiAPIError(f"Ошибка удаления записи: {res.get('message')}")
        return res

    def cancel(self, appointment_id: str | int) -> dict[str, Any]:
        """Алиас для remove()."""
        return self.remove(appointment_id)