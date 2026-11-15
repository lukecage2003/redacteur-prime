from pathlib import Path

import pytest

from primestone.storage import LocalObjectStore, ObjectNotFoundError, create_object_store


@pytest.fixture
def store(tmp_path: Path) -> LocalObjectStore:
    return LocalObjectStore(tmp_path / "store")


def test_put_and_read_bytes(store: LocalObjectStore) -> None:
    store.put_bytes("renders/ab/page.webp", b"data", "image/webp")
    assert store.exists("renders/ab/page.webp")
    assert store.size("renders/ab/page.webp") == 4
    with store.open("renders/ab/page.webp") as fh:
        assert fh.read() == b"data"


def test_put_file(store: LocalObjectStore, tmp_path: Path) -> None:
    source = tmp_path / "x.pdf"
    source.write_bytes(b"%PDF-1.4 test")
    store.put_file("originals/x.pdf", source, "application/pdf")
    with store.local_copy("originals/x.pdf") as path:
        assert path.read_bytes() == b"%PDF-1.4 test"


def test_overwrite_is_atomic_and_leaves_no_temp_file(store: LocalObjectStore) -> None:
    store.put_bytes("a/b", b"1", "text/plain")
    store.put_bytes("a/b", b"2", "text/plain")
    with store.open("a/b") as fh:
        assert fh.read() == b"2"
    assert [p.name for p in (store.root / "a").iterdir()] == ["b"]


@pytest.mark.parametrize("key", ["../evil", "/etc/passwd", "a/../../b", "", "a//b", ".hidden"])
def test_invalid_keys_rejected(store: LocalObjectStore, key: str) -> None:
    with pytest.raises(ValueError, match="clé"):
        store.put_bytes(key, b"x", "text/plain")


def test_missing_object(store: LocalObjectStore) -> None:
    assert not store.exists("nope")
    with pytest.raises(ObjectNotFoundError):
        store.open("nope")
    with pytest.raises(ObjectNotFoundError), store.local_copy("nope"):
        pass


def test_factory(tmp_path: Path) -> None:
    assert isinstance(create_object_store("local", tmp_path), LocalObjectStore)
    with pytest.raises(ValueError, match="GCS_BUCKET"):
        create_object_store("gcs", tmp_path)  # bucket obligatoire
    with pytest.raises(ValueError, match="inconnu"):
        create_object_store("s3", tmp_path)
