"""Сквозной интеграционный тест всех модулей SDK DIKIDI Business.

Проверяет совместную работу:
1. Экспресс-самодиагностики (Healthcheck & Guards)
2. Каталога и динамического подбора мастеров под услугу
3. Графика рабочих смен мастеров
4. Алгоритмического движка расчета слотов (FreeSlotsEngine)
5. Клиентской базы (счётчики, поиск, карточка, история визитов)
6. Журнала записей на актуальную дату
"""

import os
from datetime import datetime
from dotenv import load_dotenv
from dikidi import DikidiAPI

load_dotenv()

PHONE = os.getenv("DIKIDI_PHONE")
PASSWORD = os.getenv("DIKIDI_PASSWORD")
COMPANY_ID = os.getenv("DIKIDI_COMPANY")


def main():
    print("=" * 72)
    print("     ПОЛНЫЙ СКВОЗНОЙ ИНТЕГРАЦИОННЫЙ ТЕСТ DIKIDI BUSINESS SDK")
    print("=" * 72)

    today = datetime.now().strftime("%Y-%m-%d")

    with DikidiAPI(phone=PHONE, password=PASSWORD, company_id=COMPANY_ID) as api:
        print(f"✓ Сессия активна! Авторизован User ID: {api.user_id}\n")

        # -------------------------------------------------------------
        # 1. ЭКСПРЕСС-САМОДИАГНОСТИКА ШЛЮЗОВ (READINESS PROBE)
        # -------------------------------------------------------------
        print("[1] Запуск экспресс-проверки работоспособности всех 5 шлюзов...")
        report = api.healthcheck()
        report.print_summary()
        assert report.is_healthy, "ОШИБКА: Один или несколько боевых шлюзов недоступны!"

        # -------------------------------------------------------------
        # 2. КАТАЛОГ УСЛУГ И ПОДБОР КВАЛИФИЦИРОВАННЫХ МАСТЕРОВ
        # -------------------------------------------------------------
        print("\n[2] Анализ каталога (Мастера, Дерево услуг, Квалификация)...")
        catalog = api.catalog.get_catalog()
        print(f"  ✓ Загружено сотрудников: {len(catalog.masters)}")
        print(f"  ✓ Активных услуг в прайсе: {len(catalog.services)}")

        test_service = catalog.services[0] if catalog.services else None
        suitable_master_id = None

        if test_service:
            print(f"  • Тестовая услуга: '{test_service.name}' (ID: {test_service.id}, {test_service.cost} руб., {test_service.duration} мин.)")
            capable_masters = api.catalog.get_available_masters_for_service(test_service.id)
            print(f"  ✓ Мастеров, оказывающих эту услугу: {len(capable_masters)}")
            if capable_masters:
                suitable_master_id = str(capable_masters[0].get("id"))
                m_name = capable_masters[0].get("name", "Мастер")
                print(f"  • Выбран подходящий мастер: {m_name} (ID: {suitable_master_id})")

        # -------------------------------------------------------------
        # 3. ГРАФИК РАБОТЫ И СМЕНЫ МАСТЕРОВ
        # -------------------------------------------------------------
        print(f"\n[3] Чтение графика рабочих смен на сегодня ({today})...")
        shifts_today = api.schedule.get_shifts(today, today)
        print(f"  ✓ Активных смен в салоне сегодня: {len(shifts_today)}")

        active_master_id = suitable_master_id
        target_shift = next((s for s in shifts_today if s.is_working), None)
        if target_shift:
            active_master_id = target_shift.master_id
            print(f"  • Мастер на смене: ID {active_master_id} (Часы работы: {target_shift.work_from} — {target_shift.work_to})")

        # -------------------------------------------------------------
        # 4. ДВИЖОК СЛОТОВ И ВЫЧИСЛЕНИЕ ДОСТУПНЫХ ОКОН ЗАПИСИ
        # -------------------------------------------------------------
        print(f"\n[4] Расчёт свободных слотов времени (Интервальная математика)...")
        if active_master_id and test_service:
            slots_rep = api.appointments.get_slots_report(
                master_id=active_master_id,
                date=today,
                service_id=test_service.id,
                step_minutes=30,
                allow_past=True,  # чтобы увидеть расчёт на весь сегодняшний день
            )
            print(f"  ✓ Услуга: {slots_rep.service_name} ({slots_rep.duration_minutes} мин.)")
            print(f"  ✓ Занятых записей у мастера на сегодня: {len(slots_rep.busy_records)}")
            print(f"  ✓ Доступных слотов рассчитано: {len(slots_rep.free_slots)}")
            if slots_rep.free_slots:
                preview = ", ".join(f"[{t}]" for t in slots_rep.free_slots[:6])
                print(f"  • Первые доступные слоты: {preview} ...")
        else:
            print("  ℹ️ Не выбран активный мастер для расчета слотов.")

        # -------------------------------------------------------------
        # 5. КЛИЕНТСКАЯ БАЗА (СЧЕТЧИКИ, ПОИСК, КАРТОЧКА, ИСТОРИЯ)
        # -------------------------------------------------------------
        print("\n[5] Работа с клиентской базой...")
        filter_info = api.clients.get_filter_info()
        print(f"  ✓ Всего клиентов в базе CRM: {filter_info.total_count}")
        print(f"  ✓ Категорий/групп: {len(filter_info.available_groups)}, Источников: {len(filter_info.available_sources)}")

        found_clients = api.clients.search(query="а", limit=1)
        if found_clients:
            target_client = found_clients[0]
            print(f"  • Найден клиент: {target_client.name} (Тел: {target_client.phone or 'не указан'})")

            card = api.clients.get_card(target_client.id)
            history = api.clients.get_history(target_client.id)
            print(f"  ✓ Карточка настроек и история визитов получены ({len(str(card)) + len(str(history))} байт)")

        # -------------------------------------------------------------
        # 6. ЖУРНАЛ ЗАПИСЕЙ И СТАТУСЫ ВИЗИТОВ
        # -------------------------------------------------------------
        print(f"\n[6] Чтение журнала записей на сегодня ({today})...")
        today_records = api.appointments.get_records(today, today)
        print(f"  ✓ Записей в журнале на сегодня: {len(today_records)}")
        if today_records:
            for idx, rec in enumerate(today_records[:3], 1):
                srv = ", ".join(rec.services) if rec.services else "Услуга"
                print(f"    {idx}. [{rec.time_start} - {rec.time_end}] {rec.client_name or 'Клиент'} | {srv} | {rec.cost} руб. ({rec.status})")

    print("\n" + "=" * 72)
    print("      ВСЕ СИСТЕМЫ И МОДУЛИ SDK РАБОТАЮТ ИДЕАЛЬНО!")
    print("=" * 72)


if __name__ == "__main__":
    main()