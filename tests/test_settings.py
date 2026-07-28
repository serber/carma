import pytest

from carma.settings import RuntimeSettings


def test_reads_initial_value():
    settings = RuntimeSettings(min_confidence=0.4)
    assert settings.min_confidence == 0.4


def test_updates_value():
    settings = RuntimeSettings(min_confidence=0.0)
    settings.min_confidence = 0.7
    assert settings.min_confidence == 0.7


@pytest.mark.parametrize("value", [-0.1, 1.1, 2.0])
def test_rejects_out_of_range_value(value):
    settings = RuntimeSettings(min_confidence=0.5)
    with pytest.raises(ValueError, match="between 0 and 1"):
        settings.min_confidence = value
    assert settings.min_confidence == 0.5  # unchanged
