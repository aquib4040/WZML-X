from unittest import TestCase

from file_stream_utils import content_disposition


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
