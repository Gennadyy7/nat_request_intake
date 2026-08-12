from pathlib import Path


def normalize_absolute_base_dir(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Base directory path must be a non-empty absolute path')
    normalized = value.strip()
    if not Path(normalized).is_absolute():
        raise ValueError('Base directory path must be an absolute path')
    return normalized


def normalize_optional_absolute_base_dir(value: object) -> str | None:
    if value is None:
        return None
    return normalize_absolute_base_dir(value)
