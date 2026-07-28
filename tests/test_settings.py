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


def test_without_persist_path_nothing_is_written(tmp_path):
    settings = RuntimeSettings(min_confidence=0.0)
    settings.min_confidence = 0.6
    assert list(tmp_path.iterdir()) == []


def test_persists_across_instances(tmp_path):
    persist_path = tmp_path / "runtime_settings.json"

    first = RuntimeSettings(min_confidence=0.0, persist_path=str(persist_path))
    first.min_confidence = 0.6

    second = RuntimeSettings(min_confidence=0.0, persist_path=str(persist_path))
    assert second.min_confidence == 0.6  # persisted value wins over the config default


def test_no_persisted_file_yet_uses_config_default(tmp_path):
    persist_path = tmp_path / "runtime_settings.json"
    settings = RuntimeSettings(min_confidence=0.3, persist_path=str(persist_path))
    assert settings.min_confidence == 0.3


def test_creates_parent_directory_for_persist_path(tmp_path):
    persist_path = tmp_path / "nested" / "dir" / "runtime_settings.json"
    settings = RuntimeSettings(min_confidence=0.0, persist_path=str(persist_path))
    settings.min_confidence = 0.5
    assert persist_path.is_file()


def test_ignores_corrupt_persisted_file(tmp_path):
    persist_path = tmp_path / "runtime_settings.json"
    persist_path.write_text("not valid json")

    settings = RuntimeSettings(min_confidence=0.4, persist_path=str(persist_path))

    assert settings.min_confidence == 0.4  # falls back to config default


def test_ignores_out_of_range_persisted_value(tmp_path):
    persist_path = tmp_path / "runtime_settings.json"
    persist_path.write_text('{"min_confidence": 5.0}')

    settings = RuntimeSettings(min_confidence=0.4, persist_path=str(persist_path))

    assert settings.min_confidence == 0.4  # falls back to config default
