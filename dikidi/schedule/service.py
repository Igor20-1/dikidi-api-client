"""Сервис управления графиком работы мастеров CRM DIKIDI Business."""

import logging
from typing import Any, Sequence
from dikidi.core.config import NET_URL
from dikidi.core.transport import DikidiTransport
from dikidi.core.exceptions import DikidiAPIError
from dikidi.appointments.schemas import MasterShift
from dikidi.appointments.parser import parse_schedules
from dikidi.schedule.schemas import ShiftSetup

logger = logging.getLogger("DikidiScheduleService")


class ScheduleService:
    """Сервис управления рабочим расписанием сотрудников/мастеров."""

    def __init__(self, transport: DikidiTransport):
        self.transport = transport
        self.company_id = str(transport.config.company_id)

    def save_timetable(self, setup: ShiftSetup) -> dict[str, Any]:
        """Низкоуровневая отправка формы на шлюз timetable_edit."""
        url = f"{NET_URL}/owner/ajax/schedule/timetable_edit/?company={self.company_id}"
        headers = self.transport.get_ajax_headers(f"/ru/owner/schedule/?company={self.company_id}")

        form_payload = setup.to_form_payload()
        logger.info(
            "[SCHEDULE] Отправка изменений расписания (мастеров: %d, дат: %d, выходной: %s)...",
            len(setup.master_ids),
            len(setup.dates),
            setup.is_day_off,
        )

        resp = self.transport.request("POST", url, headers=headers, data=form_payload)
        resp.raise_for_status()

        result = resp.json() if resp.text else {}
        if isinstance(result, dict) and result.get("error", {}).get("code", 0) != 0:
            err_msg = result.get("error", {}).get("message") or "Ошибка сохранения графика"
            raise DikidiAPIError(f"DIKIDI отклонил изменение графика: {err_msg}")

        return result

    def set_shift(
        self,
        master_id: str | int,
        date: str,
        work_from: str,
        work_to: str,
        break_from: str | None = None,
        break_to: str | None = None,
    ) -> dict[str, Any]:
        """Назначает или обновляет рабочую смену мастера на выбранную дату."""
        setup = ShiftSetup(
            master_ids=[str(master_id)],
            dates=[date],
            work_begin=work_from,
            work_end=work_to,
            break_begin=break_from,
            break_end=break_to,
            is_day_off=False,
        )
        return self.save_timetable(setup)

    def set_day_off(
        self,
        master_id: str | int,
        dates: str | Sequence[str],
    ) -> dict[str, Any]:
        """Устанавливает выходной день (удаляет рабочую смену) на указанную дату или даты."""
        date_list = [dates] if isinstance(dates, str) else list(dates)
        setup = ShiftSetup(
            master_ids=[str(master_id)],
            dates=date_list,
            is_day_off=True,
        )
        return self.save_timetable(setup)

    def set_bulk_shifts(
        self,
        master_ids: str | int | Sequence[str | int],
        dates: Sequence[str],
        work_from: str,
        work_to: str,
        break_from: str | None = None,
        break_to: str | None = None,
    ) -> dict[str, Any]:
        """Пакетно назначает одинаковый график сразу на несколько дат и/или мастеров."""
        m_list = [str(master_ids)] if isinstance(master_ids, (str, int)) else [str(m) for m in master_ids]
        setup = ShiftSetup(
            master_ids=m_list,
            dates=list(dates),
            work_begin=work_from,
            work_end=work_to,
            break_begin=break_from,
            break_end=break_to,
            is_day_off=False,
        )
        return self.save_timetable(setup)

    def get_shifts(
        self,
        date_from: str,
        date_to: str,
        master_id: str | int | None = None,
    ) -> list[MasterShift]:
        """Запрашивает список рабочих смен за период (всех мастеров или конкретного)."""
        url = f"{NET_URL}/ru/owner/ajax/journal/api/?company={self.company_id}"
        headers = self.transport.get_ajax_headers(f"/ru/owner/journal/?company={self.company_id}")

        data = {
            "request[get][]": ["masters.schedules"],
            "request[options][masters][schedules][0][date_from]": date_from,
            "request[options][masters][schedules][0][date_to]": date_to,
        }

        resp = self.transport.request("POST", url, headers=headers, data=data)
        resp.raise_for_status()

        all_shifts = parse_schedules(resp.json())
        if master_id is not None:
            target_id = str(master_id)
            return [s for s in all_shifts if s.master_id == target_id]
        return all_shifts