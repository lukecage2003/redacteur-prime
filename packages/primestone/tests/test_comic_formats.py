import io
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from primestone.comic.formats import (
    DocumentFormat,
    Limits,
    RejectedDocumentError,
    detect_format,
    inspect_document,
    natural_key,
    render_page,
)

LIMITS = Limits()


def render(path: Path, fmt: DocumentFormat, n: int, dim: int = 200) -> Image.Image:
    out = render_page(path, fmt, n, max_dimension=dim, quality=80, limits=LIMITS)
    image = Image.open(io.BytesIO(out.data))
    assert image.format == "WEBP"
    assert (image.width, image.height) == (out.width, out.height)
    return image


class TestDetection:
    def test_pdf_and_cbz_by_signature(self) -> None:
        assert detect_format(b"%PDF-1.7\n...") is DocumentFormat.PDF
        assert detect_format(b"\n\n%PDF-1.4") is DocumentFormat.PDF  # en-tête décalé toléré
        assert detect_format(b"PK\x03\x04rest") is DocumentFormat.CBZ

    @pytest.mark.parametrize("head", [b"", b"hello", b"\x89PNG\r\n", b"Rar!\x1a\x07"])
    def test_unknown_rejected(self, head: bytes) -> None:
        with pytest.raises(RejectedDocumentError, match="format"):
            detect_format(head)


def test_natural_sort() -> None:
    names = ["p10.png", "p2.png", "p1.png", "P3.png"]
    assert sorted(names, key=natural_key) == ["p1.png", "p2.png", "P3.png", "p10.png"]


class TestPdf:
    def test_inspect(self, comic_factory: SimpleNamespace) -> None:
        info = inspect_document(comic_factory.pdf(pages=5), LIMITS)
        assert (info.format, info.page_count) == (DocumentFormat.PDF, 5)

    def test_render_scales_to_max_dimension(self, comic_factory: SimpleNamespace) -> None:
        image = render(comic_factory.pdf(pages=2), DocumentFormat.PDF, 2, dim=300)
        assert max(image.size) == 300
        assert image.size[1] > image.size[0]  # orientation portrait conservée

    def test_page_out_of_range(self, comic_factory: SimpleNamespace) -> None:
        with pytest.raises(RejectedDocumentError, match="inexistante"):
            render(comic_factory.pdf(pages=2), DocumentFormat.PDF, 3)

    def test_corrupt_pdf_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.pdf"
        path.write_bytes(b"%PDF-1.7\n this is not really a pdf")
        with pytest.raises(RejectedDocumentError, match="PDF"):
            inspect_document(path, LIMITS)

    def test_too_many_pages(self, comic_factory: SimpleNamespace) -> None:
        with pytest.raises(RejectedDocumentError, match="trop de pages"):
            inspect_document(comic_factory.pdf(pages=4), Limits(max_pages=3))


class TestCbz:
    def test_inspect_ignores_non_images(self, comic_factory: SimpleNamespace) -> None:
        path = comic_factory.cbz(
            pages=4,
            extra={"ComicInfo.xml": b"<ComicInfo/>", "__MACOSX/._x.png": b"x", ".DS_Store": b""},
        )
        assert inspect_document(path, LIMITS).page_count == 4

    def test_render_natural_order(self, tmp_path: Path) -> None:
        path = tmp_path / "order.cbz"
        with zipfile.ZipFile(path, "w") as archive:
            for number, color in ((10, "red"), (2, "blue"), (1, "green")):
                buffer = io.BytesIO()
                Image.new("RGB", (40, 60), color).save(buffer, format="PNG")
                archive.writestr(f"p{number}.png", buffer.getvalue())
        first = render(path, DocumentFormat.CBZ, 1).convert("RGB").getpixel((20, 30))
        last = render(path, DocumentFormat.CBZ, 3).convert("RGB").getpixel((20, 30))
        assert isinstance(first, tuple)
        assert first[1] > 100  # vert : p1
        assert isinstance(last, tuple)
        assert last[0] > 200  # rouge : p10

    def test_small_images_are_not_upscaled(self, comic_factory: SimpleNamespace) -> None:
        image = render(comic_factory.cbz(pages=1), DocumentFormat.CBZ, 1, dim=2000)
        assert image.size == (300, 450)

    def test_path_traversal_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "evil.cbz"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("../../etc/page1.png", b"x")
        with pytest.raises(RejectedDocumentError, match="suspect"):
            inspect_document(path, LIMITS)

    def test_zip_bomb_ratio_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "bomb.cbz"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("page1.png", b"\0" * 5_000_000)
        with pytest.raises(RejectedDocumentError, match="compression"):
            inspect_document(path, LIMITS)

    def test_no_pages_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.cbz"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("readme.txt", b"hello")
        with pytest.raises(RejectedDocumentError, match="aucune page"):
            inspect_document(path, LIMITS)

    def test_corrupt_archive_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "broken.cbz"
        path.write_bytes(b"PK\x03\x04" + b"garbage" * 10)
        with pytest.raises(RejectedDocumentError, match="corrompue"):
            inspect_document(path, LIMITS)

    def test_unreadable_image_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "badimg.cbz"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("page1.png", b"\x89PNG\r\n\x1a\n not an image")
        with pytest.raises(RejectedDocumentError, match="illisible"):
            render(path, DocumentFormat.CBZ, 1)

    def test_giant_image_rejected(self, comic_factory: SimpleNamespace) -> None:
        path = comic_factory.cbz(pages=1)
        with pytest.raises(RejectedDocumentError, match="trop grande"):
            render_page(
                path,
                DocumentFormat.CBZ,
                1,
                max_dimension=100,
                quality=80,
                limits=Limits(max_image_pixels=1000),
            )


class TestFileLimits:
    def test_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.pdf"
        path.write_bytes(b"")
        with pytest.raises(RejectedDocumentError, match="vide"):
            inspect_document(path, LIMITS)

    def test_too_large(self, comic_factory: SimpleNamespace) -> None:
        with pytest.raises(RejectedDocumentError, match="volumineux"):
            inspect_document(comic_factory.pdf(pages=1), Limits(max_file_bytes=10))
