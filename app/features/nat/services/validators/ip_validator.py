from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network

from app.core.config import Settings
from app.features.nat.constants import (
    InputColumnName,
    NatIpFieldName,
    ValidationErrorCode,
)


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


def validate_ip_field(
    raw_value: str,
    column: InputColumnName,
    field_name: NatIpFieldName,
    settings: Settings,
) -> IpValidationFailure | None:
    if not raw_value.strip():
        return None

    parsed = parse_ip_value(raw_value, column)
    if isinstance(parsed, IpValidationFailure):
        return parsed

    if (
        parsed.network is not None
        and field_name not in settings.NAT_CIDR_ALLOWED_FIELDS
    ):
        return IpValidationFailure(
            error_code=ValidationErrorCode.CIDR_NOT_ALLOWED,
            column=column,
        )

    if field_name == NatIpFieldName.INTERNAL_IP and not _is_beltelecom_ip(
        parsed, settings
    ):
        return IpValidationFailure(
            error_code=ValidationErrorCode.IP_NOT_BELTELECOM,
            column=column,
        )

    return None


def _is_beltelecom_ip(parsed: ParsedIpValue, settings: Settings) -> bool:
    allowed_networks = [
        IPv4Network(network, strict=False)
        for network in settings.NAT_BELTELECOM_INTERNAL_NETWORKS
    ]

    if parsed.network is not None:
        return any(parsed.network.subnet_of(allowed) for allowed in allowed_networks)

    if parsed.address is not None:
        return any(parsed.address in allowed for allowed in allowed_networks)

    return False
