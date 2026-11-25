"""Base62 encoding and decoding utilities."""

BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE = len(BASE62_ALPHABET)


def encode_base62(number: int) -> str:
    """Encode a non-negative integer as a Base62 string."""
    if isinstance(number, bool) or not isinstance(number, int):
        raise TypeError("number must be an integer")
    if number < 0:
        raise ValueError("number must be non-negative")
    if number == 0:
        return "0"

    encoded = ""
    while number > 0:
        number, remainder = divmod(number, BASE)
        encoded = BASE62_ALPHABET[remainder] + encoded
    return encoded


def decode_base62(code: str) -> int:
    """Decode a non-empty Base62 string into a non-negative integer."""
    if not isinstance(code, str):
        raise TypeError("code must be a string")
    if not code:
        raise ValueError("code must not be empty")

    number = 0
    for character in code:
        try:
            digit = BASE62_ALPHABET.index(character)
        except ValueError:
            raise ValueError(f"invalid Base62 character: {character!r}") from None
        number = number * BASE + digit
    return number
