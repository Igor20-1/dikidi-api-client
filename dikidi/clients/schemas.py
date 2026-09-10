import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Client:
    id: str
    name: str
    phone: str
    visits_count: int = 0
    last_visit: str | None = None
    discount: float = 0.0
    avg_check: float = 0.0
    spent_total: float = 0.0
    groups: list[str] = field(default_factory=list)
    comment: str | None = None
    is_blocked: bool = False
    is_deleted: bool = False
    avatar_url: str | None = None


@dataclass
class ClientCreate:
    """Модель для создания нового клиента в CRM."""
    name: str
    phone: str
    surname: str = ""
    email: str = ""
    sex: int = 0  # 0: не указан, 1: мужской, 2: женский
    birthday: str = ""  # Формат: DD/MM/YYYY
    discount: float = 0.0
    card: str = ""
    source_id: str | int = 0
    comment: str = ""
    blacklist_comment: str = ""

    def to_form_data(self) -> dict[str, str]:
        clean_phone = re.sub(r"\D", "", str(self.phone))
        return {
            "name": self.name.strip(),
            "surname": self.surname.strip(),
            "number": clean_phone,
            "email": self.email.strip(),
            "sex": str(self.sex),
            "birthday": self.birthday.strip().replace(".", "/"),
            "discount": str(self.discount),
            "card": self.card.strip(),
            "source_id": str(self.source_id),
            "comment": self.comment.strip(),
            "blacklist_comment": self.blacklist_comment.strip(),
        }


@dataclass
class ClientUpdate:
    """Модель частичного обновления клиента. Поля со значением None сохраняют текущие данные в CRM."""
    name: str | None = None
    phone: str | None = None
    surname: str | None = None
    email: str | None = None
    sex: int | None = None
    birthday: str | None = None  # Формат: DD/MM/YYYY
    discount: float | None = None
    card: str | None = None
    source_id: str | int | None = None
    comment: str | None = None
    blacklist_comment: str | None = None
    is_for_journal: int = 1

    def apply_to_form_data(self, form_data: dict[str, str]) -> dict[str, str]:
        """Накладывает только переданные поля (не None) на базовые данные клиента."""
        res = dict(form_data)
        res["is_for_journal"] = str(self.is_for_journal)

        if self.name is not None:
            res["name"] = self.name.strip()
        if self.surname is not None:
            res["surname"] = self.surname.strip()
        if self.phone is not None:
            res["number"] = re.sub(r"\D", "", str(self.phone))
        if self.email is not None:
            res["email"] = self.email.strip()
        if self.sex is not None:
            res["sex"] = str(self.sex)
        if self.birthday is not None:
            res["birthday"] = self.birthday.strip().replace(".", "/")
        if self.discount is not None:
            res["discount"] = str(self.discount)
        if self.card is not None:
            res["card"] = self.card.strip()
        if self.source_id is not None:
            res["source_id"] = str(self.source_id)
        if self.comment is not None:
            res["comment"] = self.comment.strip()
        if self.blacklist_comment is not None:
            res["blacklist_comment"] = self.blacklist_comment.strip()

        return res

    def to_form_data(self) -> dict[str, str]:
        """Генерирует форму напрямую (если текущие данные не подтягиваются из CRM)."""
        empty_form = {
            "is_for_journal": str(self.is_for_journal),
            "name": "",
            "surname": "",
            "birthday": "",
            "number": "",
            "email": "",
            "sex": "0",
            "discount": "0",
            "card": "",
            "source_id": "0",
            "comment": "",
            "blacklist_comment": "",
        }
        return self.apply_to_form_data(empty_form)


@dataclass
class ClientFilterInfo:
    total_count: int
    clients: list[Client] = field(default_factory=list)
    available_groups: dict[str, str] = field(default_factory=dict)
    available_masters: dict[str, str] = field(default_factory=dict)
    available_sources: dict[str, str] = field(default_factory=dict)