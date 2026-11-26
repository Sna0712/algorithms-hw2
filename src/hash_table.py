"""A string-key hash table using Horner hashing and separate chaining."""

from dataclasses import dataclass


@dataclass(frozen=True)
class HashStep:
    """One character's contribution to a Horner hash calculation."""

    character: str
    codepoint: int
    previous_hash: int
    current_hash: int


@dataclass(frozen=True)
class LookupTrace:
    """Details of hashing a key and searching its bucket chain."""

    steps: list[HashStep]
    bucket_index: int
    bucket_entries: list[tuple[str, object]]
    found: bool
    value: object | None
    comparisons: int


class HashTable:
    """A hash table for string keys with separate chaining collision handling."""

    def __init__(
        self,
        initial_capacity: int = 8,
        max_load: float | None = 0.75,
    ) -> None:
        if isinstance(initial_capacity, bool) or not isinstance(initial_capacity, int):
            raise TypeError("initial_capacity must be an integer")
        if initial_capacity <= 0:
            raise ValueError("initial_capacity must be positive")
        if max_load is not None and max_load <= 0:
            raise ValueError("max_load must be positive or None")

        self._capacity = initial_capacity
        self._max_load = max_load
        self._buckets: list[list[tuple[str, object]]] = [
            [] for _ in range(initial_capacity)
        ]
        self._size = 0

    @property
    def capacity(self) -> int:
        """Return the number of buckets in the table."""
        return self._capacity

    def hash_trace(
        self, key: str, capacity: int | None = None
    ) -> tuple[int, list[HashStep]]:
        """Return the Horner bucket index and each per-character hash step."""
        self._validate_key(key)
        modulus = self._capacity if capacity is None else capacity
        if isinstance(modulus, bool) or not isinstance(modulus, int):
            raise TypeError("capacity must be an integer")
        if modulus <= 0:
            raise ValueError("capacity must be positive")

        current_hash = 0
        steps = []
        for character in key:
            previous_hash = current_hash
            codepoint = ord(character)
            current_hash = (current_hash * 31 + codepoint) % modulus
            steps.append(
                HashStep(
                    character=character,
                    codepoint=codepoint,
                    previous_hash=previous_hash,
                    current_hash=current_hash,
                )
            )
        return current_hash, steps

    def hash_index(self, key: str) -> int:
        """Return the current table bucket index for key."""
        return self.hash_trace(key)[0]

    def put(self, key: str, value: object) -> None:
        """Insert or update a key and value."""
        self._validate_key(key)
        bucket_index = self.hash_index(key)
        bucket = self._buckets[bucket_index]

        for index, (stored_key, _) in enumerate(bucket):
            if stored_key == key:
                bucket[index] = (key, value)
                return

        bucket.append((key, value))
        self._size += 1
        if self._max_load is not None and self.load_factor() > self._max_load:
            self._resize(self._capacity * 2)

    def get(self, key: str) -> object | None:
        """Return a value for key, or None if the key is not present."""
        return self.get_with_comparisons(key)[0]

    def get_with_comparisons(self, key: str) -> tuple[object | None, int]:
        """Return the lookup result and number of key equality comparisons."""
        self._validate_key(key)
        bucket_index = self.hash_index(key)
        comparisons = 0
        for stored_key, value in self._buckets[bucket_index]:
            comparisons += 1
            if stored_key == key:
                return value, comparisons
        return None, comparisons

    def inspect_lookup(self, key: str) -> LookupTrace:
        """Return hash steps, bucket contents, and key comparisons for a lookup."""
        self._validate_key(key)
        bucket_index, steps = self.hash_trace(key)
        bucket_entries = self.bucket_items(bucket_index)
        comparisons = 0
        value = None
        found = False

        for stored_key, stored_value in bucket_entries:
            comparisons += 1
            if stored_key == key:
                value = stored_value
                found = True
                break

        return LookupTrace(
            steps=steps,
            bucket_index=bucket_index,
            bucket_entries=bucket_entries,
            found=found,
            value=value,
            comparisons=comparisons,
        )

    def load_factor(self) -> float:
        """Return the number of stored keys divided by the bucket count."""
        return self._size / self._capacity

    def bucket_items(self, index: int) -> list[tuple[str, object]]:
        """Return a copy of the entries in a bucket."""
        if isinstance(index, bool) or not isinstance(index, int):
            raise TypeError("bucket index must be an integer")
        if index < 0 or index >= self._capacity:
            raise IndexError("bucket index out of range")
        return self._buckets[index].copy()

    def items(self) -> list[tuple[str, object]]:
        """Return a copy of every stored key/value pair."""
        return [
            entry
            for bucket in self._buckets
            for entry in bucket
        ]

    def __len__(self) -> int:
        return self._size

    def _resize(self, new_capacity: int) -> None:
        old_buckets = self._buckets
        self._capacity = new_capacity
        self._buckets = [[] for _ in range(new_capacity)]

        for bucket in old_buckets:
            for key, value in bucket:
                bucket_index = self.hash_index(key)
                self._buckets[bucket_index].append((key, value))

    @staticmethod
    def _validate_key(key: str) -> None:
        if not isinstance(key, str):
            raise TypeError("key must be a string")
