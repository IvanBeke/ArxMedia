from typing import Protocol

from ...models import DataTransferJob


class ImportProvider(Protocol):
    def prepare(self, content: bytes) -> dict: ...

    def apply(self, job: DataTransferJob, content: bytes, import_mode: str) -> None: ...
