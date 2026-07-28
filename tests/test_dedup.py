from carma.pipeline.dedup import Deduper


def test_first_sighting_is_recorded():
    deduper = Deduper(window_seconds=30)
    assert deduper.should_record("123ABC02", now=0.0) is True


def test_repeat_within_window_is_suppressed():
    deduper = Deduper(window_seconds=30)
    deduper.should_record("123ABC02", now=0.0)
    assert deduper.should_record("123ABC02", now=10.0) is False


def test_repeat_after_window_is_recorded_again():
    deduper = Deduper(window_seconds=30)
    deduper.should_record("123ABC02", now=0.0)
    assert deduper.should_record("123ABC02", now=31.0) is True


def test_different_plates_are_independent():
    deduper = Deduper(window_seconds=30)
    assert deduper.should_record("123ABC02", now=0.0) is True
    assert deduper.should_record("A123BC77", now=0.1) is True


def test_zero_window_never_suppresses():
    deduper = Deduper(window_seconds=0)
    deduper.should_record("123ABC02", now=0.0)
    assert deduper.should_record("123ABC02", now=0.0000001) is True
