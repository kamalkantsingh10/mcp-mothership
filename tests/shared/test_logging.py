"""Tests for shared/logging_config.py — stderr output, log level, and log_name configuration."""

import logging
import os
import sys

from shared.logging_config import LOG_DIR, setup_logging


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

    def test_handler_includes_stderr(self):
        setup_logging("INFO")
        root = logging.getLogger()
        stderr_handlers = [
            h for h in root.handlers
            if isinstance(h, logging.StreamHandler) and h.stream is sys.stderr
        ]
        assert len(stderr_handlers) == 1

    def test_no_duplicate_handlers_on_repeated_calls(self):
        setup_logging("INFO")
        setup_logging("DEBUG")
        root = logging.getLogger()
        assert len(root.handlers) == 2  # stderr + file

    def test_messages_below_level_not_emitted(self, capsys):
        setup_logging("ERROR")
        logger = logging.getLogger("test_filter")
        logger.debug("should not appear")
        logger.info("should not appear")
        logger.warning("should not appear")

        captured = capsys.readouterr()
        assert captured.err == ""
        assert captured.out == ""

    def test_log_name_default_creates_server_log(self):
        setup_logging("INFO")
        expected_path = os.path.join(LOG_DIR, "server.log")
        root = logging.getLogger()
        from logging.handlers import RotatingFileHandler
        file_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
        assert len(file_handlers) == 1
        assert file_handlers[0].baseFilename == expected_path

    def test_log_name_custom_creates_named_log(self):
        setup_logging("INFO", log_name="imagen")
        expected_path = os.path.join(LOG_DIR, "imagen.log")
        root = logging.getLogger()
        from logging.handlers import RotatingFileHandler
        file_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
        assert len(file_handlers) == 1
        assert file_handlers[0].baseFilename == expected_path

    def test_log_format_uses_space_separators(self, capsys):
        setup_logging("DEBUG")
        logger = logging.getLogger("test_format")
        logger.info("format check")

        captured = capsys.readouterr()
        # New format: %(asctime)s %(levelname)s %(name)s %(message)s
        # Should NOT contain " - " separators from old format
        assert " - " not in captured.err
        assert "INFO" in captured.err
        assert "test_format" in captured.err
        assert "format check" in captured.err

    def test_setup_logging_custom_rotation(self):
        setup_logging("INFO", log_name="custom_rot", max_bytes=1_000_000, backup_count=5)
        root = logging.getLogger()
        from logging.handlers import RotatingFileHandler
        file_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
        assert len(file_handlers) == 1
        assert file_handlers[0].maxBytes == 1_000_000
        assert file_handlers[0].backupCount == 5

    def test_setup_logging_default_rotation_values(self):
        setup_logging("INFO")
        root = logging.getLogger()
        from logging.handlers import RotatingFileHandler
        file_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
        assert len(file_handlers) == 1
        assert file_handlers[0].maxBytes == 5_242_880
        assert file_handlers[0].backupCount == 3
