import logging

from carma.logging_setup import configure_logging


def test_sets_root_level():
    configure_logging("DEBUG")
    assert logging.getLogger().level == logging.DEBUG


def test_accepts_lowercase_level():
    configure_logging("warning")
    assert logging.getLogger().level == logging.WARNING


def test_installs_single_stream_handler():
    configure_logging("INFO")
    handlers = logging.getLogger().handlers
    assert len(handlers) == 1
    assert isinstance(handlers[0], logging.StreamHandler)


def test_reconfiguring_does_not_stack_handlers():
    configure_logging("INFO")
    configure_logging("INFO")
    assert len(logging.getLogger().handlers) == 1
