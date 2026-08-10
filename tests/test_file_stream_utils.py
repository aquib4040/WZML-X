from unittest import TestCase

from file_stream_utils import content_disposition, parse_byte_range


class ContentDispositionTest(TestCase):
    def test_unicode_filename_is_header_safe_and_preserved(self):
        header = content_disposition("Spider-Man – தமிழ் 🎬.mkv")

        header.encode("latin-1")
        self.assertIn('filename="Spider-Man .mkv"', header)
        self.assertIn("filename*=UTF-8''Spider-Man%20%E2%80%93%20", header)
        self.assertTrue(header.endswith("%20%F0%9F%8E%AC.mkv"))

    def test_header_injection_and_quoted_characters_are_sanitized(self):
        header = content_disposition('bad"\\name\r\nInjected: yes.mkv')

        self.assertNotIn("\r", header)
        self.assertNotIn("\n", header)
        self.assertIn('filename="bad\'_nameInjected: yes.mkv"', header)

    def test_empty_filename_has_a_fallback(self):
        self.assertIn('filename="telegram-file"', content_disposition(""))


class ByteRangeTest(TestCase):
    def test_explicit_range(self):
        self.assertEqual((10, 19), parse_byte_range("bytes=10-19", 100))

    def test_open_ended_range(self):
        self.assertEqual((90, 99), parse_byte_range("bytes=90-", 100))

    def test_suffix_range(self):
        self.assertEqual((90, 99), parse_byte_range("bytes=-10", 100))

    def test_end_is_clamped_to_file_size(self):
        self.assertEqual((90, 99), parse_byte_range("bytes=90-200", 100))

    def test_rejects_multiple_or_unsatisfiable_ranges(self):
        for value in ("bytes=0-1,4-5", "bytes=100-", "items=0-1", "bytes=5-4"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_byte_range(value, 100)
