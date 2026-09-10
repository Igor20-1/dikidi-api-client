"""Модели данных и структуры для управления расписанием мастеров."""

from dataclasses import dataclass, field
from typing import Any


def clean_time_hm(time_str: str | None) -> str:
    """Нормализует строку времени к строгому формату 'HH:MM'."""
    if not time_str:
        return ""
    s = str(time_str).strip()
    if " " in s:
        s = s.split(" ")[-1]
    parts = s.split(":")
    if len(parts) >= 2:
        try:
            return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
        except ValueError:
            return s
    return s


def clean_date_iso(date_str: str) -> str:
    """Нормализует дату к формату 'YYYY-MM-DD'."""
    s = str(date_str).strip()
    if "." in s:
        parts = s.split(".")
        if len(parts) == 3:
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return s


@dataclass
class TimeInterval:
    """Интервал времени (начало и конец)."""
    begin: str
    end: str

    def __post_init__(self):
        self.begin = clean_time_hm(self.begin)
        self.end = clean_time_hm(self.end)


@dataclass
class ShiftSetup:
    """Параметры для назначения, изменения или удаления смен мастеров."""
    master_ids: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    work_begin: str | None = None
    work_end: str | None = None
    break_begin: str | None = None
    break_end: str | None = None
    is_day_off: bool = False

    def to_form_payload(self) -> dict[str, Any]:
        """Преобразует модель в словарь для корректной сериализации формы в httpx."""
        payload: dict[str, Any] = {}

        # Сериализация списков дат под каждого мастера (httpx корректно разворачивает списки)
        clean_dates = [clean_date_iso(d) for d in self.dates]
        for m_id in self.master_ids:
            payload[f"masters[{m_id}][]"] = clean_dates

        payload["get_error_days"] = "1"

        # Если это НЕ выходной день и задано время работы — добавляем часы и перерыв
        if not self.is_day_off and self.work_begin and self.work_end:
            payload["work[begin]"] = clean_time_hm(self.work_begin)
            payload["work[end]"] = clean_time_hm(self.work_end)

            if self.break_begin and self.break_end:
                payload["break[begin]"] = clean_time_hm(self.break_begin)
                payload["break[end]"] = clean_time_hm(self.break_end)

        return payload