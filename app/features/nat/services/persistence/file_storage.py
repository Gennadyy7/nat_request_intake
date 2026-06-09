import asyncio
from pathlib import Path, PurePath
from uuid import UUID

from app.core.config import settings
from app.core.logging import get_logger
from app.features.nat.constants import MEDIA_TYPE_BY_EXTENSION
from app.features.nat.services.parsing.file_parser import resolve_extension

logger = get_logger(__name__)

DEFAULT_DOWNLOAD_MEDIA_TYPE = 'application/octet-stream'


class FileStorageService:
    def build_storage_path(self, *, original_filename: str, batch_id: UUID) -> str:
        path = PurePath(original_filename)
        stored_name = f'{path.stem}_{batch_id}{path.suffix}'
        return str(PurePath(settings.NAT_UPLOAD_BASE_DIR) / stored_name)

    async def save(self, *, content: bytes, storage_path: str) -> None:
        path = Path(storage_path)

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

        await asyncio.to_thread(_write)
        logger.debug('Stored intake file at path={}', storage_path)

    def delete(self, storage_path: str) -> None:
        path = Path(storage_path)
        if not path.exists():
            return
        path.unlink()
        logger.debug('Removed intake file at path={}', storage_path)

    def resolve_media_type(self, original_filename: str) -> str:
        extension = resolve_extension(original_filename)
        if extension is None:
            return DEFAULT_DOWNLOAD_MEDIA_TYPE
        return MEDIA_TYPE_BY_EXTENSION[extension]

    def resolve_safe_path(self, storage_path: str) -> Path | None:
        base_dir = Path(settings.NAT_UPLOAD_BASE_DIR).resolve()
        candidate = Path(storage_path).resolve()
        if not candidate.is_relative_to(base_dir):
            return None
        return candidate

    def is_readable_file(self, path: Path) -> bool:
        return path.is_file()
