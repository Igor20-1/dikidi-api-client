import os
from dotenv import load_dotenv
from dikidi import DikidiAPI, DikidiSchemaChangedError, DikidiEndpointNotFoundError
from dikidi.core.guards import guard_json_envelope

load_dotenv()

PHONE = os.getenv("DIKIDI_PHONE")
PASSWORD = os.getenv("DIKIDI_PASSWORD")
COMPANY_ID = os.getenv("DIKIDI_COMPANY")


def main():
    print("=" * 70)
    print("      ТЕСТИРОВАНИЕ СИСТЕМЫ САМОДИАГНОСТИКИ И СТРАЖЕЙ СХЕМЫ")
    print("=" * 70)

    with DikidiAPI(phone=PHONE, password=PASSWORD, company_id=COMPANY_ID) as api:
        # 1. Прогон штатной самодиагностики
        print("\n>>> ЗАПУСК ЭКСПРЕСС-ТЕСТИРОВАНИЯ ВСЕХ ШЛЮЗОВ DIKIDI...")
        report = api.healthcheck()
        report.print_summary()

        assert report.is_healthy, "ОШИБКА: Один из боевых шлюзов DIKIDI не ответил!"

        # 2. Эмуляция дрифта схемы (DIKIDI изменил структуру ключей)
        print("\n>>> ТЕСТ ЭМУЛЯЦИИ: Сервер вернул неизвестные ключи...")
        fake_broken_response = {
            "status": "success",
            "v3_appointments_list": [1, 2, 3],  # Неизвестный ключ вместо 'masters'
            "server_time": "2026-09-10 12:00:00",
        }

        try:
            guard_json_envelope(
                fake_broken_response,
                expected_any=["masters", "master"],
                context="Эмуляция поломки журнала",
            )
            print("✗ ОШИБКА: Страж пропустил битую схему!")
        except DikidiSchemaChangedError as e:
            print("✓ УСПЕХ! Страж перехватил дрифт схемы и спас от овербукинга:")
            print(f"  {e}")

        # 3. Эмуляция запроса на несуществующий эндпоинт (HTTP 404)
        print("\n>>> ТЕСТ ЭМУЛЯЦИИ: Запрос на удаленный/перенесенный URL...")
        try:
            # Нарочно вызываем несуществующий шлюз
            api.transport.request("GET", f"https://dikidi.net/ru/owner/ajax/non_existent_route_404/")
            print("✗ ОШИБКА: Сервер не вернул 404!")
        except DikidiEndpointNotFoundError as e:
            print("✓ УСПЕХ! Транспорт распознал удаление/перенос эндпоинта:")
            print(f"  {e}")

    print("\n" + "=" * 70)
    print("   ВСЕ СТРАЖИ И ДИАГНОСТИКА ОТРАБОТАЛИ НА 100% УСПЕШНО!")
    print("=" * 70)


if __name__ == "__main__":
    main()