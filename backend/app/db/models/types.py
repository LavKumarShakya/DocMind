"""SQLAlchemy column-type helpers."""

import enum
from typing import Any

import sqlalchemy as sa


def enum_type(enum_cls: type[enum.Enum], name: str) -> Any:
    """Non-native enum column backed by VARCHAR.

    Storing enums as strings (rather than native PostgreSQL ENUM types) keeps
    future migrations of enum values simple, while the Python enum still
    provides validation at the ORM layer.
    """
    return sa.Enum(
        enum_cls,
        name=name,
        native_enum=False,
        length=32,
        values_callable=lambda e: [member.value for member in e],
    )
