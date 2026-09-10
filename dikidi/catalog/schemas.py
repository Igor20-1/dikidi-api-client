from dataclasses import dataclass, field


@dataclass
class Master:
    id: str
    name: str
    post: str | None = None
    is_master: bool = True
    group_id: str | None = None
    avatar_url: str | None = None


@dataclass
class Service:
    id: str
    name: str
    cost: float = 0.0
    duration: int = 0  # Длительность в минутах
    category_id: str | None = None
    category_name: str | None = None


@dataclass
class Category:
    id: str
    name: str
    parent_id: str | None = None


@dataclass
class CatalogDump:
    masters: list[Master] = field(default_factory=list)
    services: list[Service] = field(default_factory=list)