import asyncio
from pathlib import Path, PurePath
from uuid import UUID

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


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
