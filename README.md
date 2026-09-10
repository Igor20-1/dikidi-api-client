# dikidi-api-client (Unofficial SDK)

[![PyPI version](https://img.shields.io/pypi/v/dikidi-api-client.svg)](https://pypi.org/project/dikidi-api-client/)
[![Python versions](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://pypi.org/project/dikidi-api-client/)[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **ЮРИДИЧЕСКИЙ ДИСКЛЕЙМЕР (LEGAL DISCLAIMER):**
> Данная библиотека является **неофициальным SDK**, разработанным независимыми инженерами исключительно в интеграционных, образовательных и исследовательских целях. Проект никак **не связан, не аффилирован, не поддерживается и не спонсируется** сервисом DIKIDI Business (ООО «ДИКИДИ»). Все товарные знаки, логотипы и коммерческие обозначения принадлежат их законным владельцам. Разработчики библиотеки не несут ответственности за возможные блокировки аккаунтов, сбои или изменения на стороне сервиса. Используя данный SDK, вы действуете на свой страх и риск.

---

**dikidi-api-client** - модульный, строго типизированный и отказоустойчивый Python SDK для взаимодействия с CRM DIKIDI Business через реверс-инжиниринг веб-API.

## Ключевые возможности

* **Надёжное ядро:** Работа по протоколу HTTP/2 (`httpx`), прозрачное авто-восстановление сессии при протухании кук (401/403/«Недостаточно прав») и проброс `XSRF-TOKEN`.
* **Умное кэширование сессии (Smart Root Anchoring):** Файл сессии автоматически привязывается к корню проекта - никаких дубликатов в подпапках или тестах.
* **Защита от сбоев бэкенда (Anti-Drift Guards):** Стражи целостности отслеживают WAF/Cloudflare, перенос эндпоинтов (404/405) и изменения структуры данных (предотвращая «тихие» пустые списки).
* **Алгоритмический движок слотов (FreeSlotsEngine):** Чистая интервальная математика вычисления свободных окон с вычетом графиков смен, перерывов, занятых броней и служебных дежурств.
* **Служебные блокировки CRM:** Автоматическое распознавание технических записей (`is_block=True`: дежурства, санобработка, личные дела мастеров).
* **Безопасное обновление клиентов (Safe Partial Merge):** Предзагрузка карточки клиента перед обновлением гарантирует, что имя, телефон, email или день рождения случайно не затрутся пустыми строками.
* **Асинхронная выгрузка базы:** Параллельное скачивание всей базы клиентов (1700+ контактов) за пару секунд через `asyncio`.
* **Управление графиком мастеров:** Назначение рабочих часов, обедов, установка выходных и пакетное (bulk) распределение смен.
* **Встроенная самодиагностика (`api.healthcheck()`):** Экспресс-проверка доступности всех 5 веб-шлюзов за 1.5 секунды (готовность к Docker / Kubernetes Readiness Probes).

---

## 📦 Установка

```bash
pip install dikidi-api-client
```

---

## Аутентификация и Конфигурация

SDK поддерживает автоматический подхват учётных данных из переменных окружения (включая файлы `.env`):

Создайте файл `.env` в корне проекта:
```env
DIKIDI_PHONE=+79000000000
DIKIDI_PASSWORD=ваш_пароль
DIKIDI_COMPANY=1400000
```

Или передайте их явно при создании фасада:
```python
from dikidi import DikidiAPI

# Вариант 1: Автоматический подхват из .env
with DikidiAPI() as api:
    pass

# Вариант 2: Явное задание параметров
with DikidiAPI(phone="+7...", password="...", company_id="1400892") as api:
    pass
```

---

## Примеры использования

### 1. Экспресс-диагностика шлюзов (Healthcheck)
Перед запуском бота или приложения можно убедиться в доступности API:

```python
from dikidi import DikidiAPI

with DikidiAPI() as api:
    report = api.healthcheck()
    report.print_summary()

    if not report.is_healthy:
        print("Внимание: один из шлюзов недоступен!")
```

---

### 2. Каталог услуг и подбор мастеров

```python
from dikidi import DikidiAPI

with DikidiAPI() as api:
    # Получение полного каталога (мастера и дерево услуг)
    catalog = api.catalog.get_catalog()
    print(f"Мастеров: {len(catalog.masters)}, Услуг: {len(catalog.services)}")

    # Динамический подбор мастеров, которые могут оказать конкретную услугу
    SERVICE_ID = "19575651"
    capable_masters = api.catalog.get_available_masters_for_service(SERVICE_ID)
    for m in capable_masters:
        print(f"Мастер: {m.get('name')} (ID: {m.get('id')})")
```

---

### 3. Расчёт свободных окон для записи (Slots Engine)

Движок самостоятельно сопоставляет график смены мастера, вычитает перерывы на обед, текущие записи клиентов и служебные дежурства:

```python
from dikidi import DikidiAPI

with DikidiAPI() as api:
    # Плоский список доступного времени (формат HH:MM)
    free_slots = api.appointments.get_free_slots(
        master_id="4259767",
        date="2026-09-15",
        duration_minutes=120,  # Продолжительность услуги (минут)
        step_minutes=30,       # Шаг сетки
    )
    print("Свободные слоты:", free_slots)

    # Или подробный диагностический отчёт дня
    report = api.appointments.get_slots_report(
        master_id="4259767",
        date="2026-09-15",
        service_id="19575651",
    )
    print(f"Смена: {report.shift.work_from} - {report.shift.work_to}")
    print(f"Занятых записей в CRM: {len(report.busy_records)}")
    print(f"Окон доступно: {len(report.free_slots)}")
```

---

### 4. Бронирование, перенос и статусы визитов

```python
from dikidi import DikidiAPI, BookingRequest

with DikidiAPI() as api:
    # 1. Сквозная онлайн-запись (холдирование слота + сохранение)
    booking = BookingRequest(
        master_id="4259767",
        service_ids=["19575651"],
        time_str="2026-09-15 14:00:00",
        client_name="Иван Иванов",
        client_phone="+79991112233",
        comment="Запись через Telegram-бота",
    )
    result = api.appointments.book(booking)
    print("Запись успешно создана! Ответ CRM:", result)

    # 2. Получение записей журнала за период
    records = api.appointments.get_records("2026-09-15", "2026-09-15")
    for r in records:
        if r.is_block:
            print(f"[Служебный блок]: {r.time_start}-{r.time_end} | {r.client_name}")
        else:
            print(f"Запись: {r.time_start}-{r.time_end} | {r.client_name} ({r.cost} руб.)")

    # 3. Перенос записи на другую дату/время
    if records:
        api.appointments.reschedule(records[0], new_date="2026-09-16", new_time="15:30")

    # 4. Отметка визита («Клиент пришел»: came_id=1, подтверждена: is_accept=1)
    if records:
        api.appointments.change_status(records[0], came_id=1, is_accept=1)
```

---

### 5. Безопасное управление клиентами (Safe Merge)

```python
from dikidi import DikidiAPI, ClientUpdate

with DikidiAPI() as api:
    # Поиск клиентов по имени или номеру телефона
    clients = api.clients.search(query="Иван", limit=5)

    if clients:
        client = clients[0]

        # Безопасное обновление: обновляем ТОЛЬКО скидку и комментарий.
        # Имя, телефон, дата рождения и email подтянутся из CRM и НЕ затрутся!
        api.clients.update(
            client_id=client.id,
            client_data=ClientUpdate(discount=10.0, comment="VIP-клиент"),
        )

        # Просмотр карточки и истории визитов
        history = api.clients.get_history(client.id)
```

---

### 6. Управление графиком смен мастеров

```python
from dikidi import DikidiAPI

with DikidiAPI() as api:
    # 1. Назначение рабочей смены с перерывом на обед
    api.schedule.set_shift(
        master_id="4259767",
        date="2026-09-20",
        work_from="09:00",
        work_to="18:00",
        break_from="13:00",
        break_to="14:00",
    )

    # 2. Установка выходного дня (удаление смены)
    api.schedule.set_day_off(master_id="4259767", dates="2026-09-21")

    # 3. Пакетное проставление смен на неделю сразу для группы мастеров
    api.schedule.set_bulk_shifts(
        master_ids=["4259767", "3951121"],
        dates=["2026-09-22", "2026-09-23", "2026-09-24"],
        work_from="10:00",
        work_to="19:00",
    )
```

---

## Отказоустойчивость и безопасность

Библиотека содержит собственный слой стражей (`guards.py`), защищающий ваше приложение от:
* `DikidiEndpointNotFoundError` - вызов перенесённых или удалённых DIKIDI шлюзов (HTTP 404 / 405).
* `DikidiWAFBlockedError` - выявление блокировок Cloudflare, капчи или rate-limit.
* `DikidiSchemaChangedError` - перехват изменения ключей в JSON-ответах CRM с подробным дампом структуры для предотвращения овербукинга.

---

## 📄 Лицензия

Проект распространяется под свободной лицензией **MIT**. Подробности в файле [LICENSE](LICENSE).
