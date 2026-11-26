"""FirestoreFileStorage against a minimal in-memory imitation of the Firestore API."""

from io import BytesIO

import pytest
from firebase_admin import firestore

from app.storage import file_storage
from app.storage.file_storage import MASK, SCAN, FirestoreFileStorage


class FakeSnapshot:
    def __init__(self, ref, data):
        self.reference, self._data = ref, data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data)


class FakeDocument:
    def __init__(self, store, path):
        self._store, self._path = store, path

    def collection(self, name):
        return FakeCollection(self._store, f"{self._path}/{name}")

    def get(self):
        return FakeSnapshot(self, self._store.get(self._path))

    def set(self, data):
        self._store[self._path] = dict(data)

    def update(self, data):
        if self._path not in self._store:
            raise KeyError(self._path)
        doc = self._store[self._path]
        for key, value in data.items():
            if value is firestore.DELETE_FIELD:
                doc.pop(key, None)
            else:
                doc[key] = value

    def delete(self):
        self._store.pop(self._path, None)


class FakeCollection:
    def __init__(self, store, path):
        self._store, self._path = store, path

    def document(self, doc_id):
        return FakeDocument(self._store, f"{self._path}/{doc_id}")

    def stream(self):
        prefix = self._path + "/"
        for path in [p for p in self._store if p.startswith(prefix)
                     and "/" not in p[len(prefix):]]:
            yield FakeSnapshot(FakeDocument(self._store, path), self._store[path])

    def order_by(self, field):
        docs = sorted(self.stream(), key=lambda snap: snap.to_dict()[field])
        return type("Query", (), {"stream": lambda self_: iter(docs)})()


class FakeFirestore:
    def __init__(self):
        self.store = {"patients/p1": {"name": "Ion"}}

    def collection(self, name):
        return FakeCollection(self.store, name)

    def chunk_paths(self):
        return [p for p in self.store if "_chunks/" in p]


@pytest.fixture
def db(monkeypatch):
    fake = FakeFirestore()
    monkeypatch.setattr(file_storage, "get_db", lambda: fake)
    return fake


SMALL = b"s" * 1000
LARGE = b"L" * (2 * 1024 * 1024)   # chunked


@pytest.mark.parametrize("content", [SMALL, LARGE])
def test_save_and_load_roundtrip(db, content):
    storage = FirestoreFileStorage()
    storage.save("p1", BytesIO(content), "scan.nii.gz", SCAN)
    loaded = storage.load("p1", SCAN)
    assert loaded.data == content and loaded.filename == "scan.nii.gz"
    assert bool(db.chunk_paths()) == (content is LARGE)


def test_replacing_a_chunked_file_with_a_small_one_returns_the_new_file(db):
    # Bug fixed: the old `_is_chunked` flag stayed True and `load` kept returning the
    # previous file from its chunks.
    storage = FirestoreFileStorage()
    storage.save("p1", BytesIO(LARGE), "old.nii.gz", SCAN)
    storage.save("p1", BytesIO(SMALL), "new.nii.gz", SCAN)
    loaded = storage.load("p1", SCAN)
    assert loaded.data == SMALL and loaded.filename == "new.nii.gz"
    assert db.chunk_paths() == []                         # old chunks removed


def test_replacing_a_small_file_with_a_chunked_one_drops_the_inline_copy(db):
    storage = FirestoreFileStorage()
    storage.save("p1", BytesIO(SMALL), "old.nii.gz", SCAN)
    storage.save("p1", BytesIO(LARGE), "new.nii.gz", SCAN)
    assert storage.load("p1", SCAN).data == LARGE
    assert SCAN not in db.store["patients/p1"]            # no stale base64 left behind


def test_delete_all_removes_every_chunk(db):
    # Bug fixed: deleting a patient left its chunk subcollections (the medical data)
    # in Firestore, because Firestore does not delete subcollections with the parent.
    storage = FirestoreFileStorage()
    storage.save("p1", BytesIO(LARGE), "scan.nii.gz", SCAN)
    storage.save("p1", BytesIO(LARGE), "mask.nii.gz", MASK)
    assert db.chunk_paths()
    storage.delete_all("p1")
    assert db.chunk_paths() == []


def test_delete_one_file_keeps_the_others(db):
    storage = FirestoreFileStorage()
    storage.save("p1", BytesIO(SMALL), "scan.nii.gz", SCAN)
    storage.save("p1", BytesIO(LARGE), "mask.nii.gz", MASK)
    storage.delete("p1", MASK)
    assert storage.load("p1", MASK) is None
    assert storage.load("p1", SCAN).data == SMALL
    assert db.chunk_paths() == []
