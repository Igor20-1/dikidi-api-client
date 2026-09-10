import os
from pathlib import Path
from dotenv import load_dotenv
from dikidi.core.config import DikidiConfig
from dikidi.core.transport import DikidiTransport
from dikidi.clients.service import ClientService
from dikidi.catalog.service import CatalogService
from dikidi.appointments.service import AppointmentService
from dikidi.schedule.service import ScheduleService
from dikidi.core.diagnostics import DiagnosticsRunner, HealthCheckReport

load_dotenv()

class DikidiAPI:

    def __init__(
        self,
        phone: str | None = None,
        password: str | None = None,
        company_id: str | int | None = None,
        session_file: str | Path = "session_cookies.json",
        timeout: float = 25.0,
    ):
        p = phone or os.getenv("DIKIDI_PHONE")
        pwd = password or os.getenv("DIKIDI_PASSWORD")
        cid = company_id or os.getenv("DIKIDI_COMPANY")

        if not all([p, pwd, cid]):
            raise ValueError(
                "Не переданы обязательные параметры авторизации DIKIDI (phone, password, company_id) "
                "и они не найдены в переменных окружения (DIKIDI_PHONE, DIKIDI_PASSWORD, DIKIDI_COMPANY)."
            )

        self.config = DikidiConfig(
            phone=str(p),
            password=str(pwd),
            company_id=str(cid),
            session_file=str(session_file),
            timeout=timeout,
        )
        self.transport = DikidiTransport(self.config)

        self.clients = ClientService(self.transport)
        self.catalog = CatalogService(self.transport)
        self.appointments = AppointmentService(self.transport)
        self.schedule = ScheduleService(self.transport)

    @property
    def user_id(self) -> str | None:
        return self.transport.user_id

    def ensure_auth(self) -> None:
        self.transport.ensure_auth()

    def healthcheck(self) -> HealthCheckReport:
        """Проводит экспресс-диагностику состояния всех веб-шлюзов CRM."""
        return DiagnosticsRunner(self).run()

    def close(self) -> None:
        self.transport.close()

    def __enter__(self):
        self.transport.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.transport.__exit__(exc_type, exc_val, exc_tb)