from carma.pipeline.watchlist import Watchlist


def test_disabled_never_matches():
    watchlist = Watchlist(enabled=False, plates=["ABC"])
    assert watchlist.matches("123ABC02") is False


def test_empty_plates_never_matches():
    watchlist = Watchlist(enabled=True, plates=[])
    assert watchlist.matches("123ABC02") is False


def test_full_match():
    watchlist = Watchlist(enabled=True, plates=["123ABC02"])
    assert watchlist.matches("123ABC02") is True


def test_partial_match():
    watchlist = Watchlist(enabled=True, plates=["ABC02"])
    assert watchlist.matches("123ABC02") is True


def test_no_match():
    watchlist = Watchlist(enabled=True, plates=["XYZ"])
    assert watchlist.matches("123ABC02") is False


def test_matches_cyrillic_entry_against_latin_ocr_output():
    # a watchlist entry typed with Cyrillic homoglyphs should still match
    # the OCR output, which is always plain latin/digit.
    watchlist = Watchlist(enabled=True, plates=["А123ВС77"])
    assert watchlist.matches("A123BC77") is True
