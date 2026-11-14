"""Formats de comics (PDF, CBZ) : détection, inspection et rendu des pages.

Tout fichier importé est considéré comme hostile :
- le format est détecté par signature (octets magiques), jamais par l'extension ;
- les PDF sont ouverts avec PDFium (moteur durci de Chrome) ; chiffrés ou illisibles → rejet ;
- les archives CBZ ne sont jamais extraites sur disque ; chemins suspects, entrées chiffrées,
  taux de compression anormaux (bombes zip) et images géantes sont rejetés ;
- le nombre de pages et la taille des fichiers sont bornés.
"""

from __future__ import annotations

import io
import re
import warnings
import zipfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath

import pypdfium2 as pdfium
from PIL import Image

IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"})
MAX_COMPRESSION_RATIO = 200  # au-delà : bombe zip probable
MAX_CBZ_ENTRY_BYTES = 200 * 1024 * 1024


class DocumentFormat(StrEnum):
    PDF = "PDF"
    CBZ = "CBZ"


class RejectedDocumentError(ValueError):
    """Le document (ou une page) est invalide : rejet définitif, sans nouvelle tentative."""


@dataclass(frozen=True)
class Limits:
    max_file_bytes: int = 1024**3
    max_pages: int = 2000
    max_image_pixels: int = 150_000_000


@dataclass(frozen=True)
class DocumentInfo:
    format: DocumentFormat
    page_count: int


@dataclass(frozen=True)
class RenderedPage:
    data: bytes
    width: int
    height: int


def detect_format(head: bytes) -> DocumentFormat:
    """Format d'après les premiers octets (au moins 1024 recommandés)."""
    if b"%PDF-" in head[:1024]:
        return DocumentFormat.PDF
    if head[:4] == b"PK\x03\x04":
        return DocumentFormat.CBZ
    raise RejectedDocumentError("format non reconnu (PDF ou CBZ attendu)")


def detect_file_format(path: Path) -> DocumentFormat:
    with path.open("rb") as fh:
        return detect_format(fh.read(1024))


def natural_key(name: str) -> tuple[tuple[int, int | str], ...]:
    """Tri « naturel » : page2 avant page10."""
    parts = re.split(r"(\d+)", name.lower())
    return tuple((0, int(p)) if p.isdigit() else (1, p) for p in parts if p)


def _cbz_page_names(archive: zipfile.ZipFile) -> list[str]:
    names: list[str] = []
    for info in archive.infolist():
        if info.is_dir():
            continue
        path = PurePosixPath(info.filename.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts:
            raise RejectedDocumentError(f"chemin suspect dans l'archive : {info.filename!r}")
        if info.flag_bits & 0x1:
            raise RejectedDocumentError("archive CBZ chiffrée")
        if any(part.startswith(".") or part == "__MACOSX" for part in path.parts):
            continue
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue  # ComicInfo.xml, notes… ignorés
        if info.file_size > MAX_CBZ_ENTRY_BYTES:
            raise RejectedDocumentError(f"image trop volumineuse dans l'archive : {path.name}")
        if info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
            raise RejectedDocumentError("taux de compression anormal (bombe zip ?)")
        names.append(info.filename)
    return sorted(names, key=natural_key)


def inspect_document(path: Path, limits: Limits) -> DocumentInfo:
    """Valide le document et compte ses pages. Lève RejectedDocumentError si invalide."""
    size = path.stat().st_size
    if size == 0:
        raise RejectedDocumentError("fichier vide")
    if size > limits.max_file_bytes:
        raise RejectedDocumentError(f"fichier trop volumineux ({size} octets)")
    fmt = detect_file_format(path)
    if fmt is DocumentFormat.PDF:
        try:
            pdf = pdfium.PdfDocument(path)
        except pdfium.PdfiumError as exc:
            raise RejectedDocumentError(
                f"PDF illisible ou protégé par mot de passe ({exc})"
            ) from exc
        try:
            count = len(pdf)
        finally:
            pdf.close()
    else:
        try:
            with zipfile.ZipFile(path) as archive:
                count = len(_cbz_page_names(archive))
        except zipfile.BadZipFile as exc:
            raise RejectedDocumentError(f"archive CBZ corrompue ({exc})") from exc
    if count == 0:
        raise RejectedDocumentError("aucune page")
    if count > limits.max_pages:
        raise RejectedDocumentError(f"trop de pages ({count} > {limits.max_pages})")
    return DocumentInfo(format=fmt, page_count=count)


def _encode_webp(image: Image.Image, quality: int) -> RenderedPage:
    if image.mode not in ("RGB", "RGBA", "L"):
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="WEBP", quality=quality, method=4)
    return RenderedPage(data=buffer.getvalue(), width=image.width, height=image.height)


def _render_pdf_page(path: Path, page_number: int, max_dimension: int) -> Image.Image:
    try:
        pdf = pdfium.PdfDocument(path)
    except pdfium.PdfiumError as exc:
        raise RejectedDocumentError(f"PDF illisible ({exc})") from exc
    try:
        if not 1 <= page_number <= len(pdf):
            raise RejectedDocumentError(f"page {page_number} inexistante")
        page = pdf[page_number - 1]
        try:
            width, height = page.get_size()
            if width <= 0 or height <= 0:
                raise RejectedDocumentError(f"page {page_number} de dimensions nulles")
            scale = max_dimension / max(width, height)
            image: Image.Image = page.render(scale=scale).to_pil()
            return image
        finally:
            page.close()
    finally:
        pdf.close()


def _render_cbz_page(
    path: Path, page_number: int, max_dimension: int, max_pixels: int
) -> Image.Image:
    try:
        with zipfile.ZipFile(path) as archive:
            names = _cbz_page_names(archive)
            if not 1 <= page_number <= len(names):
                raise RejectedDocumentError(f"page {page_number} inexistante")
            data = archive.read(names[page_number - 1])
    except zipfile.BadZipFile as exc:
        raise RejectedDocumentError(f"archive CBZ corrompue ({exc})") from exc
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(data))
            if image.width * image.height > max_pixels:
                raise RejectedDocumentError(
                    f"page {page_number} : image trop grande ({image.width}x{image.height})"
                )
            image.load()
    except (OSError, Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise RejectedDocumentError(f"page {page_number} : image illisible ({exc})") from exc
    image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
    return image


def render_page(
    path: Path,
    fmt: DocumentFormat,
    page_number: int,
    *,
    max_dimension: int,
    quality: int,
    limits: Limits,
) -> RenderedPage:
    """Rend une page en WebP, plus grand côté ≤ max_dimension (agrandi pour les PDF vectoriels)."""
    if fmt is DocumentFormat.PDF:
        image = _render_pdf_page(path, page_number, max_dimension)
    else:
        image = _render_cbz_page(path, page_number, max_dimension, limits.max_image_pixels)
    return _encode_webp(image, quality)
