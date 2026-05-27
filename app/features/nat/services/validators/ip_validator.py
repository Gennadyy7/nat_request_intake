from ipaddress import IPv4Network

from app.core.config import settings
from app.features.nat.constants import (
    InputColumnName,
    NatIpFieldName,
    ValidationErrorCode,
)
from app.features.nat.services.ip_parsing import (
    IpValidationFailure,
    ParsedIpValue,
    parse_ip_value,
)
from app.features.nat.services.optional_field import is_missing_optional_value


def validate_ip_field(
    raw_value: str,
    column: InputColumnName,
    field_name: NatIpFieldName,
) -> IpValidationFailure | None:
    if is_missing_optional_value(raw_value):
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

    if field_name == NatIpFieldName.INTERNAL_IP and not _is_beltelecom_ip(parsed):
        return IpValidationFailure(
            error_code=ValidationErrorCode.IP_NOT_BELTELECOM,
            column=column,
        )

    return None


def _is_beltelecom_ip(parsed: ParsedIpValue) -> bool:
    allowed_networks = [
        IPv4Network(network, strict=False)
        for network in settings.NAT_BELTELECOM_INTERNAL_NETWORKS
    ]

    if parsed.network is not None:
        return any(parsed.network.subnet_of(allowed) for allowed in allowed_networks)

    if parsed.address is not None:
        return any(parsed.address in allowed for allowed in allowed_networks)

    return False
