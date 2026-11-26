import unittest

from src.hash_table import HashTable
from src.linear_probing import LinearProbingHashTable
from src.shortener import URLShortener


class URLShortenerTests(unittest.TestCase):
    def test_shorten_and_expand_url(self):
        shortener = URLShortener()
        url = "https://example.com/a/path?query=value"

        code = shortener.shorten(url)

        self.assertEqual(code, "1")
        self.assertEqual(shortener.expand(code), url)

    def test_duplicate_url_returns_existing_code(self):
        shortener = URLShortener()
        url = "https://example.com/page"

        first_code = shortener.shorten(url)
        duplicate_code = shortener.shorten(url)

        self.assertEqual(duplicate_code, first_code)

    def test_distinct_urls_receive_distinct_codes(self):
        shortener = URLShortener()

        first_code = shortener.shorten("http://example.com/first")
        second_code = shortener.shorten("https://example.com/second")

        self.assertNotEqual(first_code, second_code)

    def test_invalid_urls_raise_value_error(self):
        shortener = URLShortener()

        invalid_urls = (
            "",
            "   ",
            "ftp://example.com/file",
            "https:///missing-host",
            None,
            42,
        )
        for url in invalid_urls:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    shortener.shorten(url)

    def test_expanding_unknown_code_raises_key_error(self):
        shortener = URLShortener()

        with self.assertRaises(KeyError):
            shortener.expand("not-registered")

    def test_shortener_round_trip_and_duplicates_with_both_table_types(self):
        url = "https://example.com/uses-linear-or-chaining"
        for resolution in ("separate_chaining", "linear_probing"):
            with self.subTest(resolution=resolution):
                shortener = URLShortener(collision_resolution=resolution)
                expected_table_type = (
                    HashTable
                    if resolution == "separate_chaining"
                    else LinearProbingHashTable
                )

                code, created = shortener.shorten_with_status(url)
                duplicate_code, duplicate_created = shortener.shorten_with_status(url)

                self.assertEqual(shortener.collision_resolution, resolution)
                self.assertIsInstance(shortener._url_to_code, expected_table_type)
                self.assertIsInstance(shortener._code_to_url, expected_table_type)
                self.assertTrue(created)
                self.assertFalse(duplicate_created)
                self.assertEqual(duplicate_code, code)
                self.assertEqual(shortener.expand(code), url)

    def test_unknown_collision_resolution_is_rejected(self):
        with self.assertRaises(ValueError):
            URLShortener(collision_resolution="unknown")


if __name__ == "__main__":
    unittest.main()
