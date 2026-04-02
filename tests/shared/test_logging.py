"""Tests for shared/logging.py — stderr output and log level configuration."""

import logging
import sys

from shared.logging import setup_logging


class TestSetupLogging:
    """Verify logging configuration."""

    def setup_method(self):
        """Reset root logger before each test."""
        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(logging.WARNING)

    def test_logging_goes_to_stderr(self, capsys):
        setup_logging("DEBUG")
        logger = logging.getLogger("test_stderr")
        logger.info("test message")

        captured = capsys.readouterr()
        assert captured.out == ""  # stdout must be empty (reserved for MCP)
        assert "test message" in captured.err

    def test_log_level_configurable_debug(self):
        setup_logging("DEBUG")
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_log_level_configurable_warning(self):
        setup_logging("WARNING")
        root = logging.getLogger()
        assert root.level == logging.WARNING

    def test_log_level_configurable_error(self):
        setup_logging("ERROR")
        root = logging.getLogger()
        assert root.level == logging.ERROR

    def test_invalid_log_level_defaults_to_info(self):
        setup_logging("INVALID_LEVEL")
        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_case_insensitive_log_level(self):
        setup_logging("debug")
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_handler_is_stderr(self):
        setup_logging("INFO")
        root = logging.getLogger()
        assert len(root.handlers) == 1
        handler = root.handlers[0]
        assert isinstance(handler, logging.StreamHandler)
        assert handler.stream is sys.stderr

    def test_no_duplicate_handlers_on_repeated_calls(self):
        setup_logging("INFO")
        setup_logging("DEBUG")
        root = logging.getLogger()
        assert len(root.handlers) == 1

    def test_messages_below_level_not_emitted(self, capsys):
        setup_logging("ERROR")
        logger = logging.getLogger("test_filter")
        logger.debug("should not appear")
        logger.info("should not appear")
        logger.warning("should not appear")

        captured = capsys.readouterr()
        assert captured.err == ""
        assert captured.out == ""
