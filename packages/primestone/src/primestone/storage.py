"""Stockage objet (PDF originaux, pages rendues, médias).

Clés relatives de type « originals/ab/abcd….pdf ». Implémentations :
- `LocalObjectStore` : développement et tests (système de fichiers, écritures atomiques) ;
- GCS : à implémenter avant le premier déploiement (buckets privés, URL signées).
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import BinaryIO, Protocol, runtime_checkable

_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9][A-Za-z0-9._-]*)*$")


class ObjectNotFoundError(KeyError):
    pass


def validate_key(key: str) -> str:
    """Refuse les clés absolues, vides, avec « .. » ou caractères inattendus."""
    if not _KEY.fullmatch(key) or ".." in key.split("/"):
        raise ValueError(f"clé de stockage invalide : {key!r}")
    return key


@runtime_checkable
class ObjectStore(Protocol):
    def put_file(self, key: str, source: Path, content_type: str) -> None: ...

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None: ...

    def exists(self, key: str) -> bool: ...

    def size(self, key: str) -> int: ...

    def open(self, key: str) -> BinaryIO: ...

    def local_copy(self, key: str) -> AbstractContextManager[Path]: ...


class LocalObjectStore:
    """Stockage sur disque. Les écritures passent par un fichier temporaire puis un renommage
    atomique : un arrêt brutal ne laisse jamais d'objet partiel sous une clé valide."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / validate_key(key)).resolve()
        if self.root not in path.parents:
            raise ValueError(f"clé hors du stockage : {key!r}")
        return path

    def _write_atomic(self, key: str, write: Callable[[BinaryIO], None]) -> None:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as fh:
                write(fh)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, target)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def put_file(self, key: str, source: Path, content_type: str) -> None:
        def write(fh: BinaryIO) -> None:
            with source.open("rb") as src:
                shutil.copyfileobj(src, fh, length=1024 * 1024)

        self._write_atomic(key, write)

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        def write(fh: BinaryIO) -> None:
            fh.write(data)

        self._write_atomic(key, write)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def size(self, key: str) -> int:
        path = self._path(key)
        if not path.is_file():
            raise ObjectNotFoundError(key)
        return path.stat().st_size

    def open(self, key: str) -> BinaryIO:
        path = self._path(key)
        if not path.is_file():
            raise ObjectNotFoundError(key)
        return path.open("rb")

    @contextmanager
    def local_copy(self, key: str) -> Iterator[Path]:
        """Chemin local lisible de l'objet (ici : le fichier lui-même, sans copie)."""
        path = self._path(key)
        if not path.is_file():
            raise ObjectNotFoundError(key)
        yield path


def create_object_store(backend: str, local_root: Path) -> LocalObjectStore:
    if backend == "local":
        return LocalObjectStore(local_root)
    raise NotImplementedError(f"stockage « {backend} » non implémenté (voir ROADMAP.md)")
