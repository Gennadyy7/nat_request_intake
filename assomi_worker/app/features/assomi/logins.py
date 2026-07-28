from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LoginSet:
    """Unique SPIN logins preserving first-seen order."""

    spin_logins: tuple[str, ...]
    local_parts: tuple[str, ...]
    local_part_to_spin_login: dict[str, str]


def local_part(login: str) -> str:
    stripped = login.strip()
    if '@' not in stripped:
        return stripped
    return stripped.split('@', maxsplit=1)[0]


def build_login_set(spin_logins: list[str]) -> LoginSet:
    ordered_spin: list[str] = []
    ordered_local: list[str] = []
    mapping: dict[str, str] = {}
    for spin_login in spin_logins:
        cleaned = spin_login.strip()
        if not cleaned:
            continue
        key = local_part(cleaned)
        if not key or key in mapping:
            continue
        mapping[key] = cleaned
        ordered_local.append(key)
        ordered_spin.append(cleaned)
    return LoginSet(
        spin_logins=tuple(ordered_spin),
        local_parts=tuple(ordered_local),
        local_part_to_spin_login=mapping,
    )
