from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedRow:
    values: dict[str, str]
    raw_field_count: int


@dataclass(frozen=True, slots=True)
class ParsedFile:
    headers: list[str]
    rows: list[ParsedRow]
