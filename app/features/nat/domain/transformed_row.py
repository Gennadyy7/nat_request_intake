from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TransformedRow:
    source_row_number: int
    datetime_from: str
    datetime_to: str
    src_xlated: str
    src_port_xlated: int | None
    src: str
    src_port: int | None
    dst: str
    dst_port: int | None
    region: str
