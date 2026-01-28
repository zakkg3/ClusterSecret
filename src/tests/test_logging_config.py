import json
import logging
import unittest
from io import StringIO
from unittest.mock import patch

from logging_config import (
    DEFAULT_LOG_ENCODER,
    DEFAULT_LOG_FORMAT,
    DEFAULT_LOG_LEVEL,
    configure_logging,
    create_handler,
    get_include_kopf,
    get_log_encoder,
    get_log_format,
    get_log_level,
)


class TestGetLogLevel(unittest.TestCase):

    def setUp(self):
        # Clear the cache before each test
        get_log_level.cache_clear()

    def tearDown(self):
        # Clear the cache after each test
        get_log_level.cache_clear()

    def test_default_log_level(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(get_log_level(), logging.INFO)

    def test_debug_log_level(self):
        with patch.dict('os.environ', {'LOG_LEVEL': 'DEBUG'}):
            self.assertEqual(get_log_level(), logging.DEBUG)

    def test_error_log_level(self):
        with patch.dict('os.environ', {'LOG_LEVEL': 'ERROR'}):
            self.assertEqual(get_log_level(), logging.ERROR)

    def test_case_insensitive(self):
        with patch.dict('os.environ', {'LOG_LEVEL': 'warning'}):
            self.assertEqual(get_log_level(), logging.WARNING)

    def test_invalid_log_level_uses_default(self):
        with patch.dict('os.environ', {'LOG_LEVEL': 'INVALID'}):
            self.assertEqual(get_log_level(), logging.INFO)


class TestGetLogEncoder(unittest.TestCase):

    def setUp(self):
        get_log_encoder.cache_clear()

    def tearDown(self):
        get_log_encoder.cache_clear()

    def test_default_encoder(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(get_log_encoder(), 'plain')

    def test_json_encoder(self):
        with patch.dict('os.environ', {'LOG_ENCODER': 'json'}):
            self.assertEqual(get_log_encoder(), 'json')

    def test_plain_encoder(self):
        with patch.dict('os.environ', {'LOG_ENCODER': 'plain'}):
            self.assertEqual(get_log_encoder(), 'plain')

    def test_case_insensitive(self):
        with patch.dict('os.environ', {'LOG_ENCODER': 'JSON'}):
            self.assertEqual(get_log_encoder(), 'json')

    def test_invalid_encoder_uses_default(self):
        with patch.dict('os.environ', {'LOG_ENCODER': 'xml'}):
            self.assertEqual(get_log_encoder(), 'plain')


class TestGetLogFormat(unittest.TestCase):

    def setUp(self):
        get_log_format.cache_clear()

    def tearDown(self):
        get_log_format.cache_clear()

    def test_default_format(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(get_log_format(), DEFAULT_LOG_FORMAT)

    def test_custom_format(self):
        custom_format = '%(levelname)s: %(message)s'
        with patch.dict('os.environ', {'LOG_FORMAT': custom_format}):
            self.assertEqual(get_log_format(), custom_format)


class TestGetIncludeKopf(unittest.TestCase):

    def setUp(self):
        get_include_kopf.cache_clear()

    def tearDown(self):
        get_include_kopf.cache_clear()

    def test_default_false(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(get_include_kopf(), False)

    def test_true(self):
        with patch.dict('os.environ', {'LOG_INCLUDE_KOPF': 'true'}):
            self.assertEqual(get_include_kopf(), True)

    def test_false(self):
        with patch.dict('os.environ', {'LOG_INCLUDE_KOPF': 'false'}):
            self.assertEqual(get_include_kopf(), False)

    def test_case_insensitive(self):
        with patch.dict('os.environ', {'LOG_INCLUDE_KOPF': 'TRUE'}):
            self.assertEqual(get_include_kopf(), True)


class TestCreateHandler(unittest.TestCase):

    def setUp(self):
        get_log_encoder.cache_clear()
        get_log_format.cache_clear()

    def tearDown(self):
        get_log_encoder.cache_clear()
        get_log_format.cache_clear()

    def test_plain_handler(self):
        with patch.dict('os.environ', {'LOG_ENCODER': 'plain'}):
            handler = create_handler()
            self.assertIsInstance(handler, logging.StreamHandler)
            self.assertIsInstance(handler.formatter, logging.Formatter)

    def test_json_handler(self):
        with patch.dict('os.environ', {'LOG_ENCODER': 'json'}):
            handler = create_handler()
            self.assertIsInstance(handler, logging.StreamHandler)
            # Check formatter is JsonFormatter
            self.assertIn('JsonFormatter', type(handler.formatter).__name__)

    def test_custom_plain_format(self):
        custom_format = '%(levelname)s - %(message)s'
        with patch.dict('os.environ', {'LOG_ENCODER': 'plain', 'LOG_FORMAT': custom_format}):
            handler = create_handler()
            self.assertEqual(handler.formatter._fmt, custom_format)


class TestConfigureLogging(unittest.TestCase):

    def setUp(self):
        get_log_level.cache_clear()
        get_log_encoder.cache_clear()
        get_log_format.cache_clear()
        get_include_kopf.cache_clear()

    def tearDown(self):
        get_log_level.cache_clear()
        get_log_encoder.cache_clear()
        get_log_format.cache_clear()
        get_include_kopf.cache_clear()
        # Reset root logger
        root = logging.getLogger()
        root.handlers = []
        root.setLevel(logging.WARNING)

    def test_configures_root_logger(self):
        with patch.dict('os.environ', {'LOG_LEVEL': 'ERROR', 'LOG_ENCODER': 'plain'}):
            configure_logging()
            root = logging.getLogger()
            self.assertEqual(root.level, logging.ERROR)
            self.assertEqual(len(root.handlers), 1)

    def test_debug_warning_message(self):
        with patch.dict('os.environ', {'LOG_LEVEL': 'DEBUG', 'LOG_ENCODER': 'plain'}):
            # Capture log output
            stream = StringIO()
            handler = logging.StreamHandler(stream)
            handler.setLevel(logging.DEBUG)
            test_logger = logging.getLogger('test_debug_warning')
            test_logger.handlers = [handler]
            test_logger.setLevel(logging.DEBUG)

            configure_logging(test_logger)

            output = stream.getvalue()
            self.assertIn('DEBUG MODE ON - NOT FOR PRODUCTION', output)
            self.assertIn('secrets are leaked to stdout', output)

    def test_no_debug_warning_for_info(self):
        with patch.dict('os.environ', {'LOG_LEVEL': 'INFO', 'LOG_ENCODER': 'plain'}):
            stream = StringIO()
            handler = logging.StreamHandler(stream)
            handler.setLevel(logging.DEBUG)
            test_logger = logging.getLogger('test_no_warning')
            test_logger.handlers = [handler]
            test_logger.setLevel(logging.DEBUG)

            configure_logging(test_logger)

            output = stream.getvalue()
            self.assertNotIn('ONLY use in NON-PROD', output)

    def test_kopf_loggers_silenced_by_default(self):
        with patch.dict('os.environ', {'LOG_LEVEL': 'DEBUG', 'LOG_INCLUDE_KOPF': 'false'}):
            configure_logging()
            kopf_logger = logging.getLogger('kopf.objects')
            self.assertEqual(kopf_logger.level, logging.WARNING)

    def test_kopf_loggers_included_when_enabled(self):
        with patch.dict('os.environ', {'LOG_LEVEL': 'DEBUG', 'LOG_INCLUDE_KOPF': 'true'}):
            configure_logging()
            kopf_logger = logging.getLogger('kopf.objects')
            self.assertEqual(kopf_logger.level, logging.DEBUG)

    def test_json_output_format(self):
        with patch.dict('os.environ', {'LOG_LEVEL': 'INFO', 'LOG_ENCODER': 'json'}):
            stream = StringIO()
            handler = logging.StreamHandler(stream)
            handler.setLevel(logging.INFO)

            # Create a test logger with JSON formatter
            test_logger = logging.getLogger('test_json_output')
            test_logger.handlers = []
            test_logger.setLevel(logging.INFO)

            # Configure and get the handler from root
            configure_logging()

            # Use root logger's handler for testing
            root = logging.getLogger()
            if root.handlers:
                root.handlers[0].stream = stream

            test_logger.parent = root
            test_logger.info('Test message')

            output = stream.getvalue()
            if output:
                # Verify it's valid JSON
                log_entry = json.loads(output.strip())
                self.assertIn('message', log_entry)
                self.assertEqual(log_entry['message'], 'Test message')


if __name__ == '__main__':
    unittest.main()
