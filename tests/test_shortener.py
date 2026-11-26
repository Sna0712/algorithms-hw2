import unittest

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


if __name__ == "__main__":
    unittest.main()
