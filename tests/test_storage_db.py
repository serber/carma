from carma.storage.db import HitStore


def test_insert_and_recent(tmp_path):
    store = HitStore(str(tmp_path / "sub" / "carma.db"))

    store.insert("2026-07-28T12:00:00+00:00", "123ABC02", 0.9, "KZ", False, "f1.jpg", "c1.jpg")
    store.insert("2026-07-28T12:01:00+00:00", "A123BC77", 0.8, "RU", True, "f2.jpg", "c2.jpg")

    hits = store.recent(limit=10)
    assert len(hits) == 2
    # most recent first
    assert hits[0].plate == "A123BC77"
    assert hits[1].plate == "123ABC02"
    assert hits[0].format == "RU"
    assert hits[0].confidence == 0.8
    assert hits[0].watchlist_match is True
    assert hits[1].watchlist_match is False

    store.close()


def test_recent_respects_limit(tmp_path):
    store = HitStore(str(tmp_path / "carma.db"))
    for i in range(5):
        store.insert(f"t{i}", f"PLATE{i}", 0.5, "unknown", False, f"f{i}.jpg", f"c{i}.jpg")

    assert len(store.recent(limit=2)) == 2
    assert len(store.recent(limit=100)) == 5
    store.close()


def test_creates_parent_directory(tmp_path):
    db_path = tmp_path / "does" / "not" / "exist" / "carma.db"
    store = HitStore(str(db_path))
    assert db_path.parent.is_dir()
    store.close()


def test_recent_on_empty_store(tmp_path):
    store = HitStore(str(tmp_path / "carma.db"))
    assert store.recent() == []
    store.close()
