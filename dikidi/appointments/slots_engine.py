"""Алгоритмический движок расчета доступных слотов времени мастера."""

import logging
from datetime import datetime
from typing import Sequence
from dikidi.appointments.schemas import MasterShift, Record

logger = logging.getLogger("DikidiSlotsEngine")


def time_to_minutes(time_str: str) -> int:
    """Переводит время 'HH:MM', 'HH:MM:SS' или 'YYYY-MM-DD HH:MM:SS' в минуты от начала суток."""
    if not time_str:
        return 0
    s = str(time_str).strip()
    if " " in s:
        s = s.split(" ")[-1]
    parts = s.split(":")
    if len(parts) >= 2:
        try:
            return int(parts[0]) * 60 + int(parts[1])
        except ValueError:
            return 0
    return 0


def minutes_to_time(minutes: int) -> str:
    """Переводит минуты от начала суток в формат 'HH:MM'."""
    hours = (minutes // 60) % 24
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Сортирует и объединяет пересекающиеся или примыкающие интервалы [start, end]."""
    if not intervals:
        return []

    valid = [(s, e) for s, e in intervals if e > s]
    if not valid:
        return []

    sorted_ints = sorted(valid, key=lambda x: x[0])
    merged = [sorted_ints[0]]

    for cur_start, cur_end in sorted_ints[1:]:
        prev_start, prev_end = merged[-1]
        if cur_start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, cur_end))
        else:
            merged.append((cur_start, cur_end))

    return merged


class FreeSlotsEngine:
    """Движок интервальной математики для расчета свободных окон записи."""

    @staticmethod
    def calculate(
        shift: MasterShift | None,
        records: Sequence[Record],
        duration_minutes: int,
        step_minutes: int = 30,
        date_str: str | None = None,
        allow_past: bool = False,
        lead_time_minutes: int = 15,
    ) -> list[str]:
        """Вычисляет список доступных стартовых слотов времени (формат 'HH:MM')."""
        if not shift or not shift.is_working:
            return []

        if duration_minutes <= 0:
            duration_minutes = step_minutes

        work_start = time_to_minutes(shift.work_from)
        work_end = time_to_minutes(shift.work_to)

        if work_end <= work_start or (work_end - work_start) < duration_minutes:
            return []

        # 1. Собираем занятые интервалы
        busy_intervals: list[tuple[int, int]] = []

        # Перерыв смены мастера
        b_start = time_to_minutes(shift.break_from)
        b_end = time_to_minutes(shift.break_to)
        if b_end > b_start and (shift.break_from != "00:00:00" or shift.break_to != "00:00:00"):
            busy_intervals.append((b_start, b_end))

        # Существующие записи
        ignored_statuses = {"отменена", "удалена", "статус #4", "статус #5"}
        for r in records:
            if r.status and r.status.strip().lower() in ignored_statuses:
                continue

            r_start = time_to_minutes(r.time_start)
            r_end = time_to_minutes(r.time_end)

            if r_end <= r_start:
                rec_dur = r.duration_minutes if r.duration_minutes > 0 else 30
                r_end = r_start + rec_dur

            busy_intervals.append((r_start, r_end))

        merged_busy = merge_intervals(busy_intervals)

        # 2. Ограничение для сегодняшнего дня
        min_allowed_minutes = 0
        if date_str and not allow_past:
            today_str = datetime.now().strftime("%Y-%m-%d")
            if date_str < today_str:
                return []
            if date_str == today_str:
                now = datetime.now()
                min_allowed_minutes = (now.hour * 60) + now.minute + lead_time_minutes

        # 3. Итерация по сетке с шагом step_minutes
        free_slots: list[str] = []
        current_time = work_start

        while (current_time + duration_minutes) <= work_end:
            slot_start = current_time
            slot_end = current_time + duration_minutes

            if slot_start >= min_allowed_minutes:
                has_collision = any(
                    max(slot_start, busy_s) < min(slot_end, busy_e)
                    for busy_s, busy_e in merged_busy
                )
                if not has_collision:
                    free_slots.append(minutes_to_time(slot_start))

            current_time += step_minutes

        return free_slots