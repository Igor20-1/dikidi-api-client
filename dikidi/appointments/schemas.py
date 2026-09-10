import random
from dataclasses import dataclass, field
from typing import Any


def format_to_dikidi_date(d_str: str) -> str:
    """Конвертирует 'YYYY-MM-DD' в формат DIKIDI 'DD.MM.YYYY'."""
    s = str(d_str).strip()
    if "-" in s:
        parts = s.split("-")
        if len(parts) == 3:
            return f"{parts[2]}.{parts[1]}.{parts[0]}"
    return s


def format_to_iso_date(d_str: str) -> str:
    """Конвертирует 'DD.MM.YYYY' в ISO 'YYYY-MM-DD'."""
    s = str(d_str).strip()
    if "." in s:
        parts = s.split(".")
        if len(parts) == 3:
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return s


@dataclass
class MasterShift:
    """Рабочая смена мастера на конкретную дату."""
    master_id: str
    date: str
    work_from: str
    work_to: str
    break_from: str = "00:00:00"
    break_to: str = "00:00:00"
    appointments_count: int = 0

    @property
    def is_working(self) -> bool:
        return self.work_from != "00:00:00" or self.work_to != "00:00:00"


@dataclass
class Record:
    """Модель записи в журнале CRM."""
    id: str
    master_id: str
    date: str
    time_start: str
    time_end: str
    duration_minutes: int = 0
    client_name: str | None = None
    client_phone: str | None = None
    client_id: str | None = None
    cost: float = 0.0
    services: list[str] = field(default_factory=list)
    status: str | None = None
    comment: str | None = None
    is_block: bool = False


@dataclass
class ReservationResult:
    record_id: str
    unique_key: str
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass
class BookingRequest:
    master_id: str | int
    service_ids: list[str | int]
    time_str: str
    client_name: str
    client_phone: str
    client_id: str | int | None = None
    comment: str = ""


@dataclass
class DaySlotsReport:
    master_id: str
    master_name: str
    date: str
    service_id: str | None
    service_name: str | None
    duration_minutes: int
    shift: MasterShift | None
    busy_records: list[Record] = field(default_factory=list)
    free_slots: list[str] = field(default_factory=list)


@dataclass
class AppointmentServiceItem:
    """Услуга в структуре редактирования записи."""
    id: str | int
    duration: int = 30
    price: float = 0.0
    cost: float = 0.0
    discount_percent: float = 0.0
    discount_sum: float = 0.0
    floating: int = 0


@dataclass
class AppointmentUpdate:
    """Модель для обновления параметров существующей записи через record_save."""
    appointment_id: str | int
    master_id: str | int
    date: str
    time: str
    client_name: str
    client_phone: str
    client_id: str | int | None = None
    services: list[AppointmentServiceItem] = field(default_factory=list)
    client_came_id: int = 0  # 0: ожидает, 1: пришел, 2: не пришел
    is_accept: int = 0       # 0: новая/не подтверждена, 1: подтверждена
    comment: str = ""
    unique_key: str | None = None
    color_label_id: int = 0

    def to_form_data(self, company_id: str) -> dict[str, str]:
        dikidi_date = format_to_dikidi_date(self.date)
        iso_date = format_to_iso_date(self.date)
        clean_time = self.time.strip()
        if len(clean_time) == 5:
            clean_time += ":00"

        key = self.unique_key or str(random.randint(10000000, 99999999))
        form: dict[str, str] = {
            "appointment_id": str(self.appointment_id),
            "clear_break": "",
            "unique_key": str(key),
            "company": str(company_id),
            "home_company": str(company_id),
            "protocol_version": "2",
            "master_id": str(self.master_id),
            "date": dikidi_date,
            "time": clean_time,
            "promocode_was_applied": "0",
            "promocode": "",
            "use_break": "0",
            "break_duration": "0",
            "client_name": self.client_name.strip(),
            "client_id": str(self.client_id or "0"),
            "client_phone": self.client_phone.strip(),
            "is_anonym": "0",
            "is_accept": str(self.is_accept),
            "client_came_id": str(self.client_came_id),
            "remind[]": "0",
            "remind_confirm": "0",
            "review": "0",
            "comments": self.comment.strip(),
            "color_label_id": str(self.color_label_id),
            "files[]": "0",
            "modal-hide-disable": "1",
        }

        # Сериализация массива услуг и ресурсов
        for idx, s in enumerate(self.services):
            prefix = f"services[{idx}]"
            form[f"{prefix}[id]"] = str(s.id)
            form[f"{prefix}[duration]"] = str(s.duration)
            form[f"{prefix}[floating]"] = str(s.floating)
            form[f"{prefix}[price]"] = f"{s.price:.2f}"
            form[f"{prefix}[discount_percent]"] = f"{s.discount_percent:.0f}"
            form[f"{prefix}[discount_sum]"] = f"{s.discount_sum:.2f}"
            form[f"{prefix}[cost]"] = f"{s.cost:.2f}"

            r_prefix = f"resources[{idx}]"
            form[f"{r_prefix}[resource_id]"] = "0"
            form[f"{r_prefix}[datetime_from]"] = f"{iso_date} "
            form[f"{r_prefix}[forServiceId]"] = ""

        return form