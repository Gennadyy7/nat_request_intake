import asyncio
import csv
from dataclasses import dataclass
from io import StringIO
from pathlib import Path, PurePath

from app.features.assomi.constants import (
    ASSOMI_CSV_DELIMITER,
    ASSOMI_CSV_HEADERS,
    ASSOMI_MISSING_FIELD_PLACEHOLDER,
    ASSOMI_OUTPUT_SUFFIX,
    SPIN_MATCHED_PATH_SUFFIX,
)
from assomi_worker.app.features.assomi.logins import LoginSet, local_part
from assomi_worker.app.features.assomi.response_parsing import AssomiAbonent


@dataclass(frozen=True, slots=True)
class AssomiCsvRow:
    contractnum: str
    login: str
    fio: str
    service_adress: str
    registration_adress: str


def collect_spin_matched_paths(output_files: list[dict[str, object]]) -> list[str]:
    indexed: list[tuple[int, str]] = []
    for item in output_files:
        raw_index = item.get('index', 0)
        raw_path = item.get('spin_matched_path')
        if not isinstance(raw_path, str) or not raw_path.strip():
            continue
        index = raw_index if isinstance(raw_index, int) else 0
        indexed.append((index, raw_path.strip()))
    indexed.sort(key=lambda pair: pair[0])
    return [path for _, path in indexed]


def resolve_safe_path(storage_path: str, *, base_dir: str) -> Path | None:
    base = Path(base_dir).resolve()
    candidate = Path(storage_path).resolve()
    if not candidate.is_relative_to(base):
        return None
    return candidate


def build_assomi_output_path(*, spin_matched_path: str, assomi_base_dir: str) -> str:
    stem_path = PurePath(spin_matched_path)
    name = stem_path.name
    if name.endswith(SPIN_MATCHED_PATH_SUFFIX):
        output_name = name[: -len(SPIN_MATCHED_PATH_SUFFIX)] + ASSOMI_OUTPUT_SUFFIX
    elif name.lower().endswith('.csv'):
        output_name = name[: -len('.csv')] + ASSOMI_OUTPUT_SUFFIX
    else:
        output_name = f'{name}{ASSOMI_OUTPUT_SUFFIX}'
    return str(PurePath(assomi_base_dir) / output_name)


def read_spin_logins_from_files(paths: list[Path]) -> list[str]:
    logins: list[str] = []
    for path in paths:
        text = _read_text_with_fallback(path)
        reader = csv.reader(StringIO(text), delimiter=ASSOMI_CSV_DELIMITER)
        for row in reader:
            if not row:
                continue
            login = row[0].strip()
            if login:
                logins.append(login)
    return logins


def build_assomi_rows(
    login_set: LoginSet,
    abonents: tuple[AssomiAbonent, ...],
) -> tuple[list[AssomiCsvRow], int, int]:
    by_local = {
        local_part(abonent.login): abonent
        for abonent in abonents
        if local_part(abonent.login)
    }
    rows: list[AssomiCsvRow] = []
    found = 0
    missing = 0
    for spin_login, key in zip(
        login_set.spin_logins,
        login_set.local_parts,
        strict=True,
    ):
        abonent = by_local.get(key)
        if abonent is None:
            missing += 1
            rows.append(
                AssomiCsvRow(
                    contractnum=ASSOMI_MISSING_FIELD_PLACEHOLDER,
                    login=spin_login,
                    fio=ASSOMI_MISSING_FIELD_PLACEHOLDER,
                    service_adress=ASSOMI_MISSING_FIELD_PLACEHOLDER,
                    registration_adress=ASSOMI_MISSING_FIELD_PLACEHOLDER,
                )
            )
            continue
        found += 1
        rows.append(
            AssomiCsvRow(
                contractnum=_value_or_placeholder(abonent.contractnum),
                login=spin_login,
                fio=_value_or_placeholder(abonent.fio),
                service_adress=_value_or_placeholder(abonent.service_adress),
                registration_adress=_value_or_placeholder(abonent.registration_adress),
            )
        )
    return rows, found, missing


async def write_assomi_csv(*, output_path: str, rows: list[AssomiCsvRow]) -> None:
    path = Path(output_path)

    def _write() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.writer(handle, delimiter=ASSOMI_CSV_DELIMITER)
            writer.writerow(ASSOMI_CSV_HEADERS)
            for row in rows:
                writer.writerow(
                    [
                        row.contractnum,
                        row.login,
                        row.fio,
                        row.service_adress,
                        row.registration_adress,
                    ]
                )

    await asyncio.to_thread(_write)


def _value_or_placeholder(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ASSOMI_MISSING_FIELD_PLACEHOLDER
    return cleaned


def _read_text_with_fallback(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ('utf-8-sig', 'cp1251'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f'Unable to decode {path} as utf-8-sig or cp1251')
