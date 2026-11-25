import unittest

from src.base62 import decode_base62, encode_base62


class Base62Tests(unittest.TestCase):
    def test_encode_known_values(self):
        self.assertEqual(encode_base62(0), "0")
        self.assertEqual(encode_base62(1), "1")
        self.assertEqual(encode_base62(61), "Z")
        self.assertEqual(encode_base62(62), "10")
        self.assertEqual(encode_base62(3843), "ZZ")
        self.assertEqual(encode_base62(3844), "100")

    def test_decode_known_values(self):
        self.assertEqual(decode_base62("0"), 0)
        self.assertEqual(decode_base62("1"), 1)
        self.assertEqual(decode_base62("Z"), 61)
        self.assertEqual(decode_base62("10"), 62)
        self.assertEqual(decode_base62("ZZ"), 3843)
        self.assertEqual(decode_base62("100"), 3844)

    def test_round_trip_large_integer(self):
        number = 10**100 + 9876543210123456789
        encoded = encode_base62(number)
        self.assertEqual(decode_base62(encoded), number)

    def test_encode_rejects_negative_integer(self):
        with self.assertRaises(ValueError):
            encode_base62(-1)

    def test_encode_rejects_invalid_input_types(self):
        for value in (1.5, "62", True, None):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    encode_base62(value)

    def test_decode_rejects_empty_string(self):
        with self.assertRaises(ValueError):
            decode_base62("")

    def test_decode_rejects_invalid_characters(self):
        for code in ("!", "0-", "é"):
            with self.subTest(code=code):
                with self.assertRaises(ValueError):
                    decode_base62(code)

    def test_decode_rejects_invalid_input_types(self):
        for code in (None, 62, b"10"):
            with self.subTest(code=code):
                with self.assertRaises(TypeError):
                    decode_base62(code)


if __name__ == "__main__":
    unittest.main()
