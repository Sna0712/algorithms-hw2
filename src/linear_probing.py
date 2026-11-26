"""A string-key hash table using Horner hashing and linear probing."""

from dataclasses import dataclass

from src.hash_table import HashStep


@dataclass(frozen=True)
class ProbeEntry:
    """One inspected slot in a linear-probing lookup."""

    slot_index: int
    key: str | None
    value: object | None
    occupied: bool
    matches: bool


@dataclass(frozen=True)
class ProbeTrace:
    """Details of a linear-probing lookup."""

    steps: list[HashStep]
    initial_bucket: int
    probes: list[ProbeEntry]
    final_slot: int
    found: bool
    value: object | None
    slot_probes: int


class LinearProbingHashTable:
    """A list-backed hash table with sequential probing for collisions."""

    def __init__(
        self,
        initial_capacity: int = 8,
        max_load: float | None = 0.75,
    ) -> None:
        if isinstance(initial_capacity, bool) or not isinstance(initial_capacity, int):
            raise TypeError("initial_capacity must be an integer")
        if initial_capacity <= 0:
            raise ValueError("initial_capacity must be positive")
        if max_load is not None:
            if isinstance(max_load, bool) or not isinstance(max_load, (int, float)):
                raise TypeError("max_load must be a number or None")
            if max_load <= 0:
                raise ValueError("max_load must be positive or None")

        self._capacity = initial_capacity
        self._max_load = max_load
        self._slots: list[tuple[str, object] | None] = [
            None for _ in range(initial_capacity)
        ]
        self._size = 0

    @property
    def capacity(self) -> int:
        """Return the number of slots in the table."""
        return self._capacity

    def hash_trace(
        self, key: str, capacity: int | None = None
    ) -> tuple[int, list[HashStep]]:
        """Return the Horner hash index and each character's intermediate value."""
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
        """Return the initial slot index for key."""
        return self.hash_trace(key)[0]

    def put(self, key: str, value: object) -> None:
        """Insert or update a key, resizing before insertion when necessary."""
        self._validate_key(key)
        slot_index, found, _probes = self._find_slot(key)
        if found:
            self._slots[slot_index] = (key, value)
            return

        if slot_index < 0:
            if self._max_load is None:
                raise OverflowError("hash table is full")
            self._resize(self._capacity * 2)
            slot_index, found, _probes = self._find_slot(key)
            if found:
                self._slots[slot_index] = (key, value)
                return

        if (
            self._max_load is not None
            and (self._size + 1) / self._capacity > self._max_load
        ):
            self._resize(self._capacity * 2)
            slot_index, found, _probes = self._find_slot(key)
            if found:
                self._slots[slot_index] = (key, value)
                return

        if slot_index < 0:
            raise OverflowError("hash table is full")
        self._slots[slot_index] = (key, value)
        self._size += 1

    def get(self, key: str) -> object | None:
        """Return the value for key, or None if it is not present."""
        return self.get_with_probes(key)[0]

    def get_with_probes(self, key: str) -> tuple[object | None, int]:
        """Return the lookup result and number of inspected slots."""
        self._validate_key(key)
        slot_index, found, probes = self._find_slot(key)
        if not found:
            return None, probes
        entry = self._slots[slot_index]
        if entry is None:
            raise RuntimeError("occupied slot disappeared during lookup")
        return entry[1], probes

    def inspect_lookup(self, key: str) -> ProbeTrace:
        """Return Horner steps and each slot inspected for a lookup."""
        initial_bucket, steps = self.hash_trace(key)
        probes: list[ProbeEntry] = []
        slot_index = initial_bucket
        found = False
        value = None
        final_slot = initial_bucket

        for _ in range(self._capacity):
            entry = self._slots[slot_index]
            final_slot = slot_index
            if entry is None:
                probes.append(
                    ProbeEntry(
                        slot_index=slot_index,
                        key=None,
                        value=None,
                        occupied=False,
                        matches=False,
                    )
                )
                break

            stored_key, stored_value = entry
            matches = stored_key == key
            probes.append(
                ProbeEntry(
                    slot_index=slot_index,
                    key=stored_key,
                    value=stored_value,
                    occupied=True,
                    matches=matches,
                )
            )
            if matches:
                found = True
                value = stored_value
                break
            slot_index = (slot_index + 1) % self._capacity

        return ProbeTrace(
            steps=steps,
            initial_bucket=initial_bucket,
            probes=probes,
            final_slot=final_slot,
            found=found,
            value=value,
            slot_probes=len(probes),
        )

    def load_factor(self) -> float:
        """Return the number of stored keys divided by the slot count."""
        return self._size / self._capacity

    def __len__(self) -> int:
        return self._size

    def _find_slot(self, key: str) -> tuple[int, bool, int]:
        slot_index = self.hash_index(key)
        for probes in range(1, self._capacity + 1):
            entry = self._slots[slot_index]
            if entry is None:
                return slot_index, False, probes
            if entry[0] == key:
                return slot_index, True, probes
            slot_index = (slot_index + 1) % self._capacity
        return -1, False, self._capacity

    def _resize(self, new_capacity: int) -> None:
        old_slots = self._slots
        self._capacity = new_capacity
        self._slots = [None for _ in range(new_capacity)]
        for entry in old_slots:
            if entry is not None:
                key, value = entry
                slot_index, found, _probes = self._find_slot(key)
                if found or slot_index < 0:
                    raise RuntimeError("failed to rehash an existing key")
                self._slots[slot_index] = (key, value)

    @staticmethod
    def _validate_key(key: str) -> None:
        if not isinstance(key, str):
            raise TypeError("key must be a string")
