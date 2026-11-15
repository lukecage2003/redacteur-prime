"""Stockage objet (PDF originaux, pages rendues, médias).

Clés relatives de type « originals/ab/abcd….pdf ». Implémentations :
- `LocalObjectStore` : développement et tests (système de fichiers, écritures atomiques) ;
- `GCSObjectStore` : cloud (bucket privé, API JSON de Cloud Storage, jeton du compte de
  service de Cloud Run via le serveur de métadonnées : aucune clé, aucune dépendance).
"""

from __future__ import annotations

import io
import os
import re
import shutil
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import Any, BinaryIO, Protocol, runtime_checkable
from urllib.parse import quote

import httpx

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


class GCSObjectStore:
    """Bucket Cloud Storage privé. Les clés sont validées comme en local ; les objets sont
    adressés par contenu (réécriture idempotente)."""

    API = "https://storage.googleapis.com"
    METADATA_URL = (  # serveur de métadonnées de Cloud Run (jeton du compte de service)
        "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
    )

    def __init__(
        self,
        bucket: str,
        *,
        transport: httpx.BaseTransport | None = None,
        token: Callable[[], str] | None = None,
    ) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]", bucket):
            raise ValueError(f"nom de bucket invalide : {bucket}")
        self._bucket = bucket
        self._http = httpx.Client(timeout=120, transport=transport)
        self._token_fn = token
        self._token: tuple[str, float] | None = None

    def _auth(self) -> dict[str, str]:
        if self._token_fn is not None:
            return {"authorization": f"Bearer {self._token_fn()}"}
        if self._token is None or self._token[1] - 60 < time.time():
            response = self._http.get(self.METADATA_URL, headers={"metadata-flavor": "Google"})
            response.raise_for_status()
            data = response.json()
            self._token = (data["access_token"], time.time() + float(data["expires_in"]))
        return {"authorization": f"Bearer {self._token[0]}"}

    def _object_url(self, key: str) -> str:
        return f"{self.API}/storage/v1/b/{self._bucket}/o/{quote(validate_key(key), safe='')}"

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        response = self._http.post(
            f"{self.API}/upload/storage/v1/b/{self._bucket}/o",
            params={"uploadType": "media", "name": validate_key(key)},
            content=data,
            headers={**self._auth(), "content-type": content_type},
        )
        response.raise_for_status()

    def put_file(self, key: str, source: Path, content_type: str) -> None:
        with source.open("rb") as fh:
            response = self._http.post(
                f"{self.API}/upload/storage/v1/b/{self._bucket}/o",
                params={"uploadType": "media", "name": validate_key(key)},
                content=fh,
                headers={**self._auth(), "content-type": content_type},
            )
        response.raise_for_status()

    def _metadata(self, key: str) -> dict[str, Any] | None:
        response = self._http.get(self._object_url(key), headers=self._auth())
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return data

    def exists(self, key: str) -> bool:
        return self._metadata(key) is not None

    def size(self, key: str) -> int:
        meta = self._metadata(key)
        if meta is None:
            raise ObjectNotFoundError(key)
        return int(meta["size"])

    def open(self, key: str) -> BinaryIO:
        response = self._http.get(
            self._object_url(key), params={"alt": "media"}, headers=self._auth()
        )
        if response.status_code == 404:
            raise ObjectNotFoundError(key)
        response.raise_for_status()
        return io.BytesIO(response.content)

    @contextmanager
    def local_copy(self, key: str) -> Iterator[Path]:
        """Copie temporaire en flux (fichiers volumineux), supprimée à la sortie."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / Path(validate_key(key)).name
            with self._http.stream(
                "GET", self._object_url(key), params={"alt": "media"}, headers=self._auth()
            ) as response:
                if response.status_code == 404:
                    raise ObjectNotFoundError(key)
                response.raise_for_status()
                with target.open("wb") as fh:
                    for chunk in response.iter_bytes(1 << 20):
                        fh.write(chunk)
            yield target


def create_object_store(
    backend: str, local_root: Path, *, gcs_bucket: str | None = None
) -> ObjectStore:
    if backend == "local":
        return LocalObjectStore(local_root)
    if backend == "gcs":
        if not gcs_bucket:
            raise ValueError("PRIMESTONE_GCS_BUCKET est requis pour le stockage gcs")
        return GCSObjectStore(gcs_bucket)
    raise ValueError(f"stockage inconnu : {backend}")
