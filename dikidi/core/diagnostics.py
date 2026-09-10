"""Модуль быстрой самодиагностики шлюзов DIKIDI API."""
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ServiceCheckResult:
    name: str
    status: str  # "OK" | "FAIL"
    latency_ms: int
    details: str
    error: str | None = None


@dataclass
class HealthCheckReport:
    timestamp: str
    is_healthy: bool
    results: list[ServiceCheckResult] = field(default_factory=list)

    def print_summary(self) -> None:
        print("=" * 70)
        print(f"        ДИАГНОСТИКА ШЛЮЗОВ DIKIDI API ({self.timestamp})")
        print("=" * 70)
        for r in self.results:
            icon = "✓" if r.status == "OK" else "✗"
            print(f" [{icon}] {r.name:<26} : {r.status:<4} ({r.latency_ms:>3} ms) | {r.details}")
            if r.error:
                print(f"     -> Причина: {r.error}")
        print("=" * 70)
        status_line = "ВСЕ ШЛЮЗЫ АКТУАЛЬНЫ И РАБОТАЮТ" if self.is_healthy else "ВНИМАНИЕ: ОБНАРУЖЕНЫ СБОИ В ШЛЮЗАХ!"
        print(f" ИТОГ: {status_line}")
        print("=" * 70)


class DiagnosticsRunner:
    """Выполняет безопасный (только чтение) опрос всех ключевых сервисов."""

    def __init__(self, api: Any):
        self.api = api

    def run(self) -> HealthCheckReport:
        results: list[ServiceCheckResult] = []
        today = datetime.now().strftime("%Y-%m-%d")

        # 1. Heartbeat / Сессия
        t0 = time.time()
        try:
            self.api.ensure_auth()  # <-- Гарантирует вход, даже если файл кук отсутствует
            alive = self.api.transport.is_session_alive()
            lat = int((time.time() - t0) * 1000)
            status = "OK" if alive else "FAIL"
            details = f"User ID: {self.api.user_id or 'unknown'}"
            err = None if alive else "timeline/count не вернул 200"
        except Exception as e:
            lat = int((time.time() - t0) * 1000)
            status, details, err = "FAIL", "Ошибка авторизации / сессии", str(e)
        results.append(ServiceCheckResult("Сессия и Heartbeat", status, lat, details, err))

        # 2. Каталог
        t0 = time.time()
        try:
            cat = self.api.catalog.get_catalog()
            lat = int((time.time() - t0) * 1000)
            status = "OK"
            details = f"Мастеров: {len(cat.masters)}, Услуг: {len(cat.services)}"
            err = None
        except Exception as e:
            lat = int((time.time() - t0) * 1000)
            status, details, err = "FAIL", "Сбой шлюза каталога", str(e)
        results.append(ServiceCheckResult("Каталог (Прайс/Мастера)", status, lat, details, err))

        # 3. Клиенты
        t0 = time.time()
        try:
            info = self.api.clients.get_filter_info()
            lat = int((time.time() - t0) * 1000)
            status = "OK"
            details = f"Всего в базе: {info.total_count} клиентов"
            err = None
        except Exception as e:
            lat = int((time.time() - t0) * 1000)
            status, details, err = "FAIL", "Сбой шлюза клиентов", str(e)
        results.append(ServiceCheckResult("База клиентов (Фильтр)", status, lat, details, err))

        # 4. Журнал записей
        t0 = time.time()
        try:
            records = self.api.appointments.get_records(today, today)
            lat = int((time.time() - t0) * 1000)
            status = "OK"
            details = f"Записей на сегодня ({today}): {len(records)}"
            err = None
        except Exception as e:
            lat = int((time.time() - t0) * 1000)
            status, details, err = "FAIL", "Сбой шлюза журнала", str(e)
        results.append(ServiceCheckResult("Журнал записей (API)", status, lat, details, err))

        # 5. График смен
        t0 = time.time()
        try:
            shifts = self.api.schedule.get_shifts(today, today)
            lat = int((time.time() - t0) * 1000)
            status = "OK"
            details = f"Смен на сегодня ({today}): {len(shifts)}"
            err = None
        except Exception as e:
            lat = int((time.time() - t0) * 1000)
            status, details, err = "FAIL", "Сбой шлюза графика", str(e)
        results.append(ServiceCheckResult("График мастеров", status, lat, details, err))

        is_healthy = all(r.status == "OK" for r in results)
        return HealthCheckReport(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            is_healthy=is_healthy,
            results=results,
        )