from dataclasses import dataclass
from datetime import datetime

from app.core.config import settings
from app.features.nat.constants import (
    InputColumnName,
    NatIpFieldName,
    TransformationErrorCode,
)
from app.features.nat.domain.validated_row import ValidatedRow
from app.features.nat.services.transformation.ip_expansion import (
    IpExpansionError,
    build_ip_axis,
    check_total_product_limit,
    iter_cartesian_product,
)
from app.features.nat.services.transformation.transformed_row import TransformedRow


@dataclass(frozen=True, slots=True)
class TransformationRowError:
    row_number: int
    error_code: TransformationErrorCode
    column: InputColumnName | None = None


@dataclass(frozen=True, slots=True)
class TransformationOutcome:
    rows: tuple[TransformedRow, ...]
    error: TransformationRowError | None


class TransformationService:
    def transform(self, validated_row: ValidatedRow) -> TransformationOutcome:
        row_number = validated_row.row_number
        datetime_from = _format_datetime(validated_row.date_from)
        datetime_to = _format_datetime(validated_row.date_to)
        region = (
            validated_row.region.value
            if validated_row.region is not None
            else settings.NAT_MISSING_FIELD_PLACEHOLDER
        )

        raw_values = {
            NatIpFieldName.INTERNAL_IP: validated_row.internal_ip,
            NatIpFieldName.EXTERNAL_IP: validated_row.external_ip,
            NatIpFieldName.RESOURCE_IP: validated_row.resource_ip,
        }

        internal_axis, internal_error = build_ip_axis(
            raw_values[NatIpFieldName.INTERNAL_IP],
            column=InputColumnName.INTERNAL_IP,
            field_name=NatIpFieldName.INTERNAL_IP,
        )
        if internal_error is not None:
            return _build_error_outcome(row_number, internal_error)

        external_axis, external_error = build_ip_axis(
            raw_values[NatIpFieldName.EXTERNAL_IP],
            column=InputColumnName.EXTERNAL_IP,
            field_name=NatIpFieldName.EXTERNAL_IP,
        )
        if external_error is not None:
            return _build_error_outcome(row_number, external_error)

        resource_axis, resource_error = build_ip_axis(
            raw_values[NatIpFieldName.RESOURCE_IP],
            column=InputColumnName.RESOURCE_IP,
            field_name=NatIpFieldName.RESOURCE_IP,
        )
        if resource_error is not None:
            return _build_error_outcome(row_number, resource_error)

        product_error = check_total_product_limit(
            (len(internal_axis), len(external_axis), len(resource_axis))
        )
        if product_error is not None:
            return TransformationOutcome(
                rows=(),
                error=TransformationRowError(
                    row_number=row_number,
                    error_code=product_error.error_code,
                    column=product_error.column,
                ),
            )

        combinations = iter_cartesian_product(
            internal_axis,
            external_axis,
            resource_axis,
        )

        transformed_rows = tuple(
            TransformedRow(
                source_row_number=row_number,
                datetime_from=datetime_from,
                datetime_to=datetime_to,
                src_xlated=external.ip,
                src_port_xlated=external.port,
                src=internal.ip,
                src_port=internal.port,
                dst=resource.ip,
                dst_port=resource.port,
                region=region,
            )
            for internal, external, resource in combinations
        )
        return TransformationOutcome(rows=transformed_rows, error=None)


def _build_error_outcome(
    row_number: int,
    expansion_error: IpExpansionError,
) -> TransformationOutcome:
    return TransformationOutcome(
        rows=(),
        error=TransformationRowError(
            row_number=row_number,
            error_code=expansion_error.error_code,
            column=expansion_error.column,
        ),
    )


def _format_datetime(value: datetime) -> str:
    naive_value = value.replace(tzinfo=None) if value.tzinfo is not None else value
    return naive_value.strftime(settings.NAT_OUTPUT_DATETIME_FORMAT)
