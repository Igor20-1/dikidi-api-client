<div align="center">

# 🗓️ dikidi-api-client

**Enterprise-Grade Unofficial Python SDK for DIKIDI Business CRM**

[![PyPI version](https://img.shields.io/pypi/v/dikidi-api-client.svg?color=blue)](https://pypi.org/project/dikidi-api-client/)
[![Python versions](https://img.shields.io/badge/Python-3.13+-3776AB.svg?logo=python&logoColor=white)](https://pypi.org/project/dikidi-api-client/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![HTTP Engine: HTTP/2](https://img.shields.io/badge/HTTP%2F2-httpx-5A29E4.svg)](https://www.python-httpx.org/)
[![CI Status](https://img.shields.io/badge/CI-passing-success.svg)](#)

Модульный, строго типизированный и отказоустойчивый Python SDK для платформы **DIKIDI Business**.
Построен на реверс-инжиниринге веб-шлюзов CRM, протоколе HTTP/2, интервальной математике расчета слотов
и многоуровневой защите от дрифта схемы данных.

<br/>

```bash
pip install dikidi-api-client
```

</div>

---

> ⚠️ **ЮРИДИЧЕСКИЙ ДИСКЛЕЙМЕР (LEGAL DISCLAIMER):**
> Данная библиотека является **неофициальным клиентским SDK**, разработанным независимыми инженерами в интеграционных и исследовательских целях. Проект **не связан, не аффилирован, не поддерживается и не сертифицирован** сервисом DIKIDI Business (ООО «ДИКИДИ»). Все товарные знаки, наименования брендов и логотипы принадлежат их законным правообладателям. Авторы не несут ответственности за блокировки аккаунтов, непредвиденные изменения на стороне CRM или финансовые риски. Используя библиотеку, вы действуете на свой страх и риск.

---

## ⚡ Ключевые преимущества перед аналогами

В отличие от простых обёрток над AJAX-запросами, `dikidi-api-client` решает фундаментальные проблемы надежности интеграций с закрытыми CRM:

| Архитектурная фича | `dikidi-api-client` | Другие неофициальные клиенты |
| :--- | :---: | :---: |
| **Сетевой протокол** | **HTTP/2 (`httpx`)** с мультиплексированием | Устаревший HTTP/1.1 (`requests`) |
| **Расчёт свободных окон** | **`FreeSlotsEngine`** (интервальная математика) | Отсутствует либо наивный перебор |
| **Учёт перерывов и дежурств** | **Да** (вычитает обеды, блокировки и график смен) | Нет (высокий риск овербукинга) |
| **Служебные блокировки** | **Авто-детекция** (`is_block=True`: дежурства/санобработка) | Ломают парсер либо теряются |
| **Обновление клиентов** | **Safe Partial Merge** (без затирания профиля) | Риск стереть телефон, email или дату рождения |
| **Защита от изменений API** | **Anti-Drift Guards** (WAF, 404/405, Schema Drift) | «Тихие» падения или пустые списки `[]` |
| **Кэширование сессии** | **Smart Root Anchoring** (к корню проекта) | Мусорные дубликаты cookies в подпапках |
| **Выгрузка базы клиентов** | **Параллельная асинхронная (`asyncio`)** | Только медленный синхронный перебор |
| **Диагностика системы** | **Встроенный `api.healthcheck()` (Readiness Probe)** | Отсутствует |

---

## 📦 Установка

Библиотека разработана для современных версий **Python 3.13+**:

```bash
pip install dikidi-api-client
```

---

## Быстрый старт

### 1. Настройка переменных окружения
Создайте файл `.env` в корневом каталоге проекта:

```env
DIKIDI_PHONE=+79000000000
DIKIDI_PASSWORD=ваш_пароль_dikidi
DIKIDI_COMPANY=1400000
```

### 2. Инициализация и самодиагностика (Healthcheck)

```python
from dikidi import DikidiAPI

# Параметры авторизации автоматически загружаются из .env
with DikidiAPI() as api:
    # Экспресс-проверка всех 5 веб-шлюзов с замером задержки (Readiness Probe)
    report = api.healthcheck()
    report.print_summary()

    if not report.is_healthy:
        raise RuntimeError("Один или несколько веб-шлюзов CRM недоступны!")

    print(f"Сессия активна! User ID: {api.user_id}")
```

---

## Практические сценарии

### 1. Расчёт свободных окон записи (FreeSlotsEngine)
Алгоритмический движок сопоставляет график смен мастера, вычитает перерывы на обед, текущие записи клиентов и технические блокировки времени (дежурства, личное время, санобработку):

```python
from dikidi import DikidiAPI

with DikidiAPI() as api:
    # Получение готового плоского списка свободного времени
    free_slots = api.appointments.get_free_slots(
        master_id="4123456",
        date="2026-09-15",
        duration_minutes=90,  # Длительность услуги в минутах
        step_minutes=30,      # Шаг сетки
    )
    print("Доступное время для записи:", free_slots)
    # -> ['10:00', '10:30', '11:00', '15:00', '15:30', '16:00']

    # Или подробный диагностический отчет за день
    report = api.appointments.get_slots_report(
        master_id="4123456",
        date="2026-09-15",
        service_id="4123456",
    )
    print(f"Мастер: {report.master_name}")
    print(f"Смена: {report.shift.work_from} - {report.shift.work_to}")
    print(f"Занятых слотов в CRM: {len(report.busy_records)}")
    print(f"Свободных слотов найдено: {len(report.free_slots)}")
```

---

### 2. Сквозное бронирование и статусы визитов

```python
from dikidi import DikidiAPI, BookingRequest

with DikidiAPI() as api:
    # Двухфазное онлайн-бронирование (холдирование слота + сохранение)
    booking = BookingRequest(
        master_id="4123456",
        service_ids=["19525641"],
        time_str="2026-09-15 14:00:00",
        client_name="Алексей Смирнов",
        client_phone="+79991234567",
        comment="Запись через Telegram-бота",
    )
    result = api.appointments.book(booking)
    print("Запись успешно создана в CRM:", result)

    # Получение записей журнала за период
    records = api.appointments.get_records("2026-09-15", "2026-09-15")
    for r in records:
        if r.is_block:
            print(f"[ТЕХНИЧЕСКИЙ БЛОК]: {r.time_start}-{r.time_end} | {r.client_name}")
        else:
            print(f"Запись: {r.time_start}-{r.time_end} | {r.client_name} ({r.cost} руб.) | {r.status}")

    # Перенос записи на другую дату/время
    if records:
        api.appointments.reschedule(records[0], new_date="2026-09-16", new_time="11:30")

    # Отметка визита («Клиент пришел»: came_id=1; подтверждена: is_accept=1)
    if records:
        api.appointments.change_status(records[0], came_id=1, is_accept=1)
```

---

### 3. Безопасное обновление клиентов (Safe Partial Merge)
В CRM DIKIDI отправка неполной формы клиента приводит к затиранию неуказанных полей (стираются дни рождения, скидки, комментарии). SDK решает это автоматически: метод `update()` предзагружает карточку клиента и объединяет существующие данные с новыми.

```python
from dikidi import DikidiAPI, ClientUpdate

with DikidiAPI() as api:
    clients = api.clients.search(query="Алексей", limit=5)

    if clients:
        target = clients[0]

        # Безопасное точечное обновление:
        # Телефон, email и дата рождения подтянутся из CRM и НЕ затрутся!
        api.clients.update(
            client_id=target.id,
            client_data=ClientUpdate(discount=15.0, comment="Постоянный VIP-гость"),
        )
```

---

### 4. Управление расписанием и сменами мастеров

```python
from dikidi import DikidiAPI

with DikidiAPI() as api:
    # Назначение рабочей смены с перерывом на обед
    api.schedule.set_shift(
        master_id="4123456",
        date="2026-09-20",
        work_from="10:00",
        work_to="20:00",
        break_from="14:00",
        break_to="15:00",
    )

    # Установка выходного дня (удаление смены)
    api.schedule.set_day_off(master_id="4259767", dates="2026-09-21")

    # Пакетное распределение расписания сразу на группу мастеров
    api.schedule.set_bulk_shifts(
        master_ids=["4123456", "4234567"],
        dates=["2026-09-22", "2026-09-23", "2026-09-24"],
        work_from="09:00",
        work_to="18:00",
    )
```

---

### 5. Высокоскоростная асинхронная выгрузка базы

```python
import asyncio
from dikidi import DikidiAPI

async def export_all():
    with DikidiAPI() as api:
        # Выгрузка всей базы (1500+ клиентов) в параллельных HTTP/2 потоках за ~2 секунды
        clients = await api.clients.get_all_async(batch_size=50, concurrency=6)
        print(f"Успешно выгружено клиентов: {len(clients)}")

asyncio.run(export_all())
```

---

## 📖 Справочник API (API Reference)

### 1. Ядро и диагностика (`DikidiAPI`)

Главный фасад для взаимодействия со всеми подсистемами CRM. Поддерживает работу в роли менеджера контекста (`with`), прозрачную реаутентификацию при истечении сессии и хранение кук с привязкой к корню проекта.

| Метод | Сигнатура / Аргументы | Описание | Возвращаемый тип |
| :--- | :--- | :--- | :--- |
| `DikidiAPI()` | `phone=None, password=None, company_id=None, session_file="session_cookies.json", timeout=25.0` | Инициализирует фасад. При отсутствии параметров читает переменные окружения `.env` | `DikidiAPI` |
| `ensure_auth()` | — | Проверяет сессию через heartbeat и при необходимости выполняет прозрачный логин | `None` |
| `healthcheck()` | — | Экспресс-тестирование доступности 5 ключевых веб-шлюзов с замером задержки | `HealthCheckReport` |
| `close()` | — | Корректно завершает и закрывает сетевую сессию `httpx.Client` | `None` |
| `user_id` | *(property)* | Возвращает ID авторизованного пользователя в экосистеме DIKIDI | `str \| None` |

---

### 2. Журнал и бронирование (`api.appointments`)

| Метод | Сигнатура / Аргументы | Описание | Возвращаемый тип |
| :--- | :--- | :--- | :--- |
| `get_records()` | `date_from: str, date_to: str` | Получение записей журнала за период (`YYYY-MM-DD`) с детекцией служебных блокировок | `list[Record]` |
| `get_schedules()` | `date_from: str, date_to: str` | Получение расписания смен мастеров за указанный диапазон дат | `list[MasterShift]` |
| `get_slots_report()` | `master_id, date, service_id=None, service_ids=None, duration_minutes=None, step_minutes=30, allow_past=False` | Формирование детального диагностического отчёта о расписании и свободных слотах | `DaySlotsReport` |
| `get_free_slots()` | `master_id, date, service_id=None, service_ids=None, duration_minutes=None, step_minutes=30, allow_past=False` | Возвращает плоский список доступного времени начала визита (`HH:MM`) | `list[str]` |
| `reserve_time()` | `master_id, service_ids, time_str, unique_key=None` | Фаза 1: временная заморозка (холдирование) слота на стороне DIKIDI | `ReservationResult` |
| `save_appointment()`| `record_id, unique_key, client_name, client_phone, client_id=None, comment=""` | Фаза 2: сохранение персональных данных клиента в захолдированный слот | `dict[str, Any]` |
| `book()` | `request: BookingRequest` | Сквозная онлайн-запись: последовательно выполняет холдирование и сохранение | `dict[str, Any]` |
| `update_record()` | `update_data: AppointmentUpdate` | Низкоуровневое обновление параметров записи в журнале (шлюз `record_save`) | `dict[str, Any]` |
| `reschedule()` | `record: Record, new_date: str, new_time: str, new_master_id=None` | Перенос существующей записи на другую дату, время или к другому мастеру | `dict[str, Any]` |
| `change_status()` | `record: Record, came_id: int = None, is_accept: int = None` | Изменение статуса (`came_id`: 1 — пришел, 2 — не пришел; `is_accept`: 1 — подтверждена) | `dict[str, Any]` |
| `remove()` / `cancel()` | `appointment_id: str \| int` | Удаление/отмена записи из журнала CRM | `dict[str, Any]` |

---

### 3. Каталог услуг и мастера (`api.catalog`)

| Метод | Сигнатура / Аргументы | Описание | Возвращаемый тип |
| :--- | :--- | :--- | :--- |
| `get_catalog()` | — | Получение полного дампа каталога: список всех мастеров и дерево категорий с услугами | `CatalogDump` |
| `get_masters()` | — | Возвращает список действующих сотрудников и мастеров компании | `list[Master]` |
| `get_services()` | — | Возвращает плоский список всех активных услуг салона с ценами и длительностью | `list[Service]` |
| `get_available_masters_for_service()` | `service_id: str \| int, date: str = None` | Динамический подбор мастеров, квалифицированных для выполнения услуги на дату | `list[dict[str, Any]]` |

---

### 4. База клиентов (`api.clients`)

| Метод | Сигнатура / Аргументы | Описание | Возвращаемый тип |
| :--- | :--- | :--- | :--- |
| `get_filter_info()` | — | Загружает метаданные клиентской базы: общее число, группы, категории и источники | `ClientFilterInfo` |
| `get_page()` | `offset=0, limit=50, query=""` | Пагинированная загрузка списка клиентов по фильтрам | `list[Client]` |
| `search()` | `query: str, limit=20` | Быстрый поиск клиентов по подстроке имени или номеру телефона | `list[Client]` |
| `get_card()` | `client_id: str \| int` | Загрузка формы и настроек профиля клиента из CRM | `dict[str, Any]` |
| `get_history()` | `client_id: str \| int` | Загрузка истории посещений и оказанных услуг конкретного клиента | `dict[str, Any]` |
| `create()` | `client_data: ClientCreate` | Создание нового клиента в CRM через шлюз `clients/save/` | `dict[str, Any]` |
| `update()` | `client_id, client_data=None, auto_fetch_current=True, **kwargs` | **Safe Partial Merge:** безопасное точечное обновление полей без затирания профиля | `dict[str, Any]` |
| `get_all_async()` | `batch_size=50, concurrency=6` | Высокоскоростная параллельная выгрузка всей базы клиентов через `asyncio` | `list[Client]` |

---

### 5. График и смены сотрудников (`api.schedule`)

| Метод | Сигнатура / Аргументы | Описание | Возвращаемый тип |
| :--- | :--- | :--- | :--- |
| `get_shifts()` | `date_from: str, date_to: str, master_id=None` | Чтение рабочих смен сотрудников за интервал дат (всех или конкретного мастера) | `list[MasterShift]` |
| `set_shift()` | `master_id, date, work_from, work_to, break_from=None, break_to=None` | Назначение или изменение рабочей смены мастера с указанием перерыва | `dict[str, Any]` |
| `set_day_off()` | `master_id, dates: str \| Sequence[str]` | Установка выходного дня (удаление рабочих смен) на одну или несколько дат | `dict[str, Any]` |
| `set_bulk_shifts()` | `master_ids, dates, work_from, work_to, break_from=None, break_to=None` | Пакетное назначение одинакового расписания группе мастеров на список дат | `dict[str, Any]` |
| `save_timetable()` | `setup: ShiftSetup` | Низкоуровневая отправка изменений расписания на веб-шлюз `timetable_edit` | `dict[str, Any]` |

---

## Архитектура отказоустойчивости

### Система стражей (Anti-Drift Guards)
Внутренний модуль `dikidi.core.guards` перехватывает нестандартные ответы инфраструктуры DIKIDI и транслирует их в строгие типизированные исключения:

```text
DikidiError (Базовый класс SDK)
├── DikidiAuthError (Сброс сессии, редирект на HTML-страницу логина)
├── DikidiAPIError (Бизнес-ошибка бэкенда DIKIDI {error: 1})
└── DikidiRequestError (Сетевые и транспортные сбои)
    ├── DikidiEndpointNotFoundError (HTTP 404/405 при переносе веб-шлюзов CRM)
    ├── DikidiWAFBlockedError (Блокировка Cloudflare, WAF, Captcha или rate-limit)
    └── DikidiSchemaChangedError (Дрифт структуры JSON: защита от овербукинга)
```

### Умное кэширование сессии (Smart Root Anchoring)
В отличие от библиотек, сохраняющих cookies в текущей рабочей директории процесса (что приводит к дублям файлов внутри `tests/` или вложенных пакетов), `dikidi-api-client` сканирует дерево каталогов вверх до корня проекта (по маркерам `.env` / `pyproject.toml`) и гарантирует централизованное переиспользование единой сессии.

---

## 📄 Лицензия

Проект распространяется под свободной лицензией **MIT**. Подробности в файле [LICENSE](LICENSE).
