from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ArtifactStatus(StrEnum):
    OK = 'ok'
    MISSING = 'missing'
    OVERSIZED = 'oversized'


@dataclass(frozen=True, slots=True)
class AssomiArtifactResolution:
    status: ArtifactStatus
    path: Path | None = None
    filename: str | None = None
    size_bytes: int | None = None


def resolve_assomi_artifact(
    output_path: str | None,
    *,
    base_dir: str,
    max_attachment_bytes: int,
) -> AssomiArtifactResolution:
    if output_path is None or not output_path.strip():
        return AssomiArtifactResolution(status=ArtifactStatus.MISSING)

    safe_path = _resolve_safe_path(output_path.strip(), base_dir=base_dir)
    if safe_path is None or not safe_path.is_file():
        return AssomiArtifactResolution(status=ArtifactStatus.MISSING)

    size_bytes = safe_path.stat().st_size
    filename = safe_path.name
    if size_bytes > max_attachment_bytes:
        return AssomiArtifactResolution(
            status=ArtifactStatus.OVERSIZED,
            path=safe_path,
            filename=filename,
            size_bytes=size_bytes,
        )
    return AssomiArtifactResolution(
        status=ArtifactStatus.OK,
        path=safe_path,
        filename=filename,
        size_bytes=size_bytes,
    )


def _resolve_safe_path(storage_path: str, *, base_dir: str) -> Path | None:
    base = Path(base_dir).resolve()
    candidate = Path(storage_path).resolve()
    if not candidate.is_relative_to(base):
        return None
    return candidate
