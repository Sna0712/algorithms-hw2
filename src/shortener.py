"""In-memory URL shortening backed by directly implemented hash tables."""

from urllib.parse import urlsplit

from src.base62 import encode_base62
from src.hash_table import HashTable, LookupTrace
from src.linear_probing import LinearProbingHashTable, ProbeTrace


def validate_url(url: str) -> str:
    """Validate an absolute HTTP(S) URL and return it without normalization."""
    if not isinstance(url, str):
        raise ValueError("url must be a string")
    if not url or url.isspace() or any(character.isspace() for character in url):
        raise ValueError("url must not be empty or contain whitespace")

    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
    except ValueError as error:
        raise ValueError("invalid URL") from error

    if parsed.scheme not in ("http", "https") or not parsed.netloc or not hostname:
        raise ValueError("url must be an absolute HTTP or HTTPS URL with a host")
    return url


class URLShortener:
    """Shorten URLs to Base62 codes and expand codes back to their URLs."""

    def __init__(self, collision_resolution: str = "separate_chaining") -> None:
        if collision_resolution not in ("separate_chaining", "linear_probing"):
            raise ValueError("unknown collision resolution method")

        table_type = (
            HashTable
            if collision_resolution == "separate_chaining"
            else LinearProbingHashTable
        )
        self._collision_resolution = collision_resolution
        self._url_to_code = table_type()
        self._code_to_url = table_type()
        self._next_id = 1

    @property
    def collision_resolution(self) -> str:
        """Return the collision strategy used by the URL and code indexes."""
        return self._collision_resolution

    def shorten(self, url: str) -> str:
        """Return a stable Base62 code for a valid URL."""
        return self.shorten_with_status(url)[0]

    def shorten_with_status(self, url: str) -> tuple[str, bool]:
        """Return the URL's code and whether a new mapping was created."""
        valid_url = validate_url(url)
        existing_code = self._url_to_code.get(valid_url)
        if existing_code is not None:
            return existing_code, False

        code = encode_base62(self._next_id)
        self._url_to_code.put(valid_url, code)
        self._code_to_url.put(code, valid_url)
        self._next_id += 1
        return code, True

    def expand(self, code: str) -> str:
        """Return the original URL for code, raising KeyError if unknown."""
        if not isinstance(code, str):
            raise TypeError("code must be a string")
        url = self._code_to_url.get(code)
        if url is None:
            raise KeyError(code)
        return url

    def inspect_url_lookup(self, url: str) -> LookupTrace | ProbeTrace:
        """Return the hash and collision-resolution trace for a valid URL."""
        return self._url_to_code.inspect_lookup(validate_url(url))

    def url_entries(self) -> list[tuple[str, object]]:
        """Return a snapshot of stored URL-to-code mappings."""
        return self._url_to_code.items()
