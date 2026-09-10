import os
from dotenv import load_dotenv
from dikidi import DikidiAPI

load_dotenv()

PHONE = os.getenv("DIKIDI_PHONE")
PASSWORD = os.getenv("DIKIDI_PASSWORD")
COMPANY_ID = os.getenv("DIKIDI_COMPANY")


def print_report_card(report, title: str):
    print("\n" + "=" * 65)
    print(f" {title}")
    print("=" * 65)
    print(f"👤 Мастер:      {report.master_name} (ID: {report.master_id})")
    print(f"📅 Дата:        {report.date}")
    print(f"💅 Услуга:      {report.service_name or 'Кастомная'} (ID: {report.service_id})")
    print(f"⏱️ Длительность: {report.duration_minutes} мин. ({report.duration_minutes / 60:.1f} ч.)")

    if report.shift:
        print(f"⏰ Смена:       {report.shift.work_from} — {report.shift.work_to}")
        if report.shift.break_from != "00:00:00":
            print(f"☕ Перерыв:     {report.shift.break_from} — {report.shift.break_to}")
    else:
        print("⏰ Смена:       Выходной / Нет смены")

    print(f"\n🔒 ЗАНЯТЫЕ ЗАПИСИ В CRM ({len(report.busy_records)}):")
    if not report.busy_records:
        print("  • Записей нет, мастер свободен весь день.")
    else:
        for r in report.busy_records:
            services_str = ", ".join(r.services) if r.services else "Услуга"
            print(f"  • [{r.time_start} - {r.time_end}] {r.client_name or 'Клиент'} | {services_str} | Статус: {r.status}")

    print(f"\n🟢 ДОСТУПНЫЕ ОКНА ДЛЯ ЗАПИСИ ({len(report.free_slots)}):")
    if report.free_slots:
        # Красивая печать по 6 слотов в строке
        chunk_size = 6
        for i in range(0, len(report.free_slots), chunk_size):
            chunk = report.free_slots[i:i + chunk_size]
            print(f"    {'   '.join(f'[{t}]' for t in chunk)}")
    else:
        print("  • Нет свободных мест")
    print("-" * 65)


def main():
    with DikidiAPI(phone=PHONE, password=PASSWORD, company_id=COMPANY_ID) as api:
        TARGET_SERVICE_ID = "19575651"  # Маникюр СТАНДАРТ

        # 1. Диагностика дня без записей (тот самый, где 17 слотов)
        report_empty = api.appointments.get_slots_report(
            master_id="4131022",
            date="2026-09-11",
            service_id=TARGET_SERVICE_ID,
            step_minutes=30,
        )
        print_report_card(report_empty, "ТЕСТ 1: ДЕНЬ БЕЗ ЗАПИСЕЙ (100% СВОБОДЕН)")

        # 2. Поиск дня с РЕАЛЬНЫМИ записями в журнале
        print("\nПоиск дня с реальной загрузкой в первой половине сентября...")
        sample_records = api.appointments.get_records("2026-09-01", "2026-09-07")

        if sample_records:
            # Берем мастера и дату из первой попавшейся записи
            busy_rec = sample_records[0]
            print(f"✓ Найдена запись мастера {busy_rec.master_id} на дату {busy_rec.date}!")

            report_busy = api.appointments.get_slots_report(
                master_id=busy_rec.master_id,
                date=busy_rec.date,
                service_id=TARGET_SERVICE_ID,
                step_minutes=30,
                allow_past=True,  # чтобы увидеть всю сетку дня ретроспективно
            )
            print_report_card(report_busy, f"ТЕСТ 2: ДЕНЬ С РЕАЛЬНОЙ ЗАГРУЗКОЙ ({busy_rec.date})")
        else:
            print("  [!] В диапазоне 01-07 сентября не найдено записей.")


if __name__ == "__main__":
    main()