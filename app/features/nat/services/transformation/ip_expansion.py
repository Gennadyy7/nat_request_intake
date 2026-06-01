from dataclasses import dataclass
from math import prod

from app.core.config import settings
from app.features.nat.constants import (
    InputColumnName,
    NatIpFieldName,
    TransformationErrorCode,
)
from app.features.nat.services.ip.parsing import ParsedIpValue, parse_ip_value


@dataclass(frozen=True, slots=True)
class IpAxisValue:
    ip: str
    port: int | None


@dataclass(frozen=True, slots=True)
class IpExpansionError:
    error_code: TransformationErrorCode
    column: InputColumnName | None


def build_ip_axis(
    raw_value: str | None,
    *,
    column: InputColumnName,
    field_name: NatIpFieldName,
) -> tuple[tuple[IpAxisValue, ...], IpExpansionError | None]:
    if raw_value is None:
        return (
            (
                IpAxisValue(
                    ip=settings.NAT_MISSING_FIELD_PLACEHOLDER,
                    port=None,
                ),
            ),
            None,
        )

    parsed = parse_ip_value(raw_value, column)
    assert isinstance(parsed, ParsedIpValue)

    port = parsed.port

    if parsed.network is not None:
        if field_name in settings.NAT_CIDR_EXPANSION_FIELDS:
            hosts = list(parsed.network.hosts())
            if not hosts:
                hosts = [parsed.network.network_address]
            if len(hosts) > settings.NAT_MAX_EXPANSION_PER_FIELD:
                return (
                    (),
                    IpExpansionError(
                        error_code=TransformationErrorCode.EXPANSION_LIMIT_EXCEEDED,
                        column=column,
                    ),
                )
            return (
                tuple(IpAxisValue(ip=str(host), port=port) for host in hosts),
                None,
            )
        return (
            (IpAxisValue(ip=str(parsed.network.network_address), port=port),),
            None,
        )

    assert parsed.address is not None
    return (IpAxisValue(ip=str(parsed.address), port=port),), None


def check_total_product_limit(
    axis_sizes: tuple[int, int, int],
) -> IpExpansionError | None:
    total = prod(axis_sizes)
    if total > settings.NAT_MAX_TOTAL_EXPANSION_PRODUCT:
        return IpExpansionError(
            error_code=TransformationErrorCode.EXPANSION_LIMIT_EXCEEDED,
            column=None,
        )
    return None


def iter_cartesian_product(
    internal_axis: tuple[IpAxisValue, ...],
    external_axis: tuple[IpAxisValue, ...],
    resource_axis: tuple[IpAxisValue, ...],
) -> list[tuple[IpAxisValue, IpAxisValue, IpAxisValue]]:
    return [
        (internal, external, resource)
        for internal in internal_axis
        for external in external_axis
        for resource in resource_axis
    ]
