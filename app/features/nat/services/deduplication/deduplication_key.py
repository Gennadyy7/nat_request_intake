from dataclasses import dataclass
from datetime import datetime
import hashlib

from app.features.nat.constants import NatRegionCode
from app.features.nat.domain.validated_row import ValidatedRow


@dataclass(frozen=True, slots=True)
class DeduplicationKey:
    date_from: datetime
    date_to: datetime
    internal_ip: str | None
    external_ip: str | None
    resource_ip: str | None
    region: NatRegionCode | None


def build_deduplication_key(validated_row: ValidatedRow) -> DeduplicationKey:
    return DeduplicationKey(
        date_from=validated_row.date_from,
        date_to=validated_row.date_to,
        internal_ip=validated_row.internal_ip,
        external_ip=validated_row.external_ip,
        resource_ip=validated_row.resource_ip,
        region=validated_row.region,
    )


def build_key_hash(key: DeduplicationKey) -> str:
    payload = '\x1f'.join(
        (
            key.date_from.isoformat(),
            key.date_to.isoformat(),
            _canonical_optional_str(key.internal_ip),
            _canonical_optional_str(key.external_ip),
            _canonical_optional_str(key.resource_ip),
            key.region.value if key.region is not None else '',
        )
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _canonical_optional_str(value: str | None) -> str:
    return value if value is not None else ''
