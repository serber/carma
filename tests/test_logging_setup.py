import logging

from carma.logging_setup import configure_logging, get_recent_logs


def test_sets_root_level():
    configure_logging("DEBUG")
    assert logging.getLogger().level == logging.DEBUG


def test_accepts_lowercase_level():
    configure_logging("warning")
    assert logging.getLogger().level == logging.WARNING


def test_installs_stream_and_buffer_handlers():
    configure_logging("INFO")
    handlers = logging.getLogger().handlers
    assert len(handlers) == 2
    assert any(isinstance(h, logging.StreamHandler) for h in handlers)


def test_reconfiguring_does_not_stack_handlers():
    configure_logging("INFO")
    configure_logging("INFO")
    assert len(logging.getLogger().handlers) == 2


def test_get_recent_logs_captures_emitted_records():
    configure_logging("INFO")
    logger = logging.getLogger("carma.test_logging_setup")
    logger.info("a distinctive test log line")

    recent = get_recent_logs()
    assert any("a distinctive test log line" in line for line in recent)


def test_get_recent_logs_respects_limit():
    configure_logging("INFO")
    logger = logging.getLogger("carma.test_logging_setup")
    for i in range(10):
        logger.info("line %d", i)

    assert len(get_recent_logs(limit=3)) == 3
