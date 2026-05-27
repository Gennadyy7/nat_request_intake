from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network

from app.features.nat.constants import InputColumnName, ValidationErrorCode


@dataclass(frozen=True, slots=True)
class IpValidationFailure:
    error_code: ValidationErrorCode
    column: InputColumnName


@dataclass(frozen=True, slots=True)
class ParsedIpValue:
    address: IPv4Address | None
    network: IPv4Network | None
    port: int | None
    raw: str


def _parse_port(port_raw: str) -> int | None:
    try:
        port = int(port_raw)
    except ValueError:
        return None
    if 1 <= port <= 65535:
        return port
    return None


def parse_ip_value(
    raw_value: str,
    column: InputColumnName,
) -> ParsedIpValue | IpValidationFailure:
    stripped = raw_value.strip()
    port: int | None = None
    ip_part = stripped

    if ':' in stripped:
        ip_part, port_raw = stripped.rsplit(':', maxsplit=1)
        parsed_port = _parse_port(port_raw)
        if parsed_port is None:
            return IpValidationFailure(
                error_code=ValidationErrorCode.INVALID_PORT,
                column=column,
            )
        port = parsed_port

    if '/' in ip_part:
        try:
            network = IPv4Network(ip_part, strict=False)
        except ValueError:
            return IpValidationFailure(
                error_code=ValidationErrorCode.INVALID_IP_FORMAT,
                column=column,
            )
        return ParsedIpValue(
            address=None,
            network=network,
            port=port,
            raw=stripped,
        )

    try:
        address = IPv4Address(ip_part)
    except ValueError:
        return IpValidationFailure(
            error_code=ValidationErrorCode.INVALID_IP_FORMAT,
            column=column,
        )

    return ParsedIpValue(
        address=address,
        network=None,
        port=port,
        raw=stripped,
    )
