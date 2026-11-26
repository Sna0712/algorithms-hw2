import unittest

from src.linear_probing import LinearProbingHashTable


class LinearProbingHashTableTests(unittest.TestCase):
    def test_uses_horner_hash_function(self):
        table = LinearProbingHashTable(initial_capacity=8, max_load=None)

        self.assertEqual(table.hash_index("abc"), 2)

    def test_collision_searches_next_slot(self):
        table = LinearProbingHashTable(initial_capacity=8, max_load=None)
        table.put("a", "first")
        table.put("i", "second")

        self.assertEqual(table.hash_index("a"), table.hash_index("i"))
        self.assertEqual(table.get("a"), "first")
        self.assertEqual(table.get("i"), "second")
        self.assertEqual(table.get_with_probes("i"), ("second", 2))

    def test_probe_wraps_from_last_slot_to_first_slot(self):
        table = LinearProbingHashTable(initial_capacity=8, max_load=None)
        table.put("g", "last-bucket")
        table.put("o", "wrapped-to-first")

        self.assertEqual(table.hash_index("g"), 7)
        self.assertEqual(table.hash_index("o"), 7)
        self.assertEqual(table.get_with_probes("g"), ("last-bucket", 1))
        self.assertEqual(table.get_with_probes("o"), ("wrapped-to-first", 2))

    def test_updating_existing_key_preserves_size(self):
        table = LinearProbingHashTable(initial_capacity=8, max_load=None)
        table.put("a", "before")
        table.put("i", "other")
        table.put("i", "after")

        self.assertEqual(len(table), 2)
        self.assertEqual(table.get("i"), "after")
        self.assertEqual(table.get_with_probes("i"), ("after", 2))

    def test_successful_and_unsuccessful_searches_count_slots(self):
        table = LinearProbingHashTable(initial_capacity=8, max_load=None)
        table.put("a", "first")
        table.put("i", "second")

        self.assertEqual(table.get_with_probes("i"), ("second", 2))
        self.assertEqual(table.get("missing"), None)

    def test_failed_search_counts_the_empty_terminating_slot(self):
        table = LinearProbingHashTable(initial_capacity=8, max_load=None)
        table.put("a", "first")
        table.put("i", "second")

        # "q" hashes to the same initial slot, then terminates at the empty slot.
        self.assertEqual(table.hash_index("q"), table.hash_index("a"))
        self.assertEqual(table.get_with_probes("q"), (None, 3))

    def test_automatic_growth_rehashes_and_preserves_entries(self):
        table = LinearProbingHashTable()
        entries = [(f"item-{index}", index) for index in range(7)]

        for key, value in entries:
            table.put(key, value)

        self.assertEqual(table.capacity, 16)
        self.assertAlmostEqual(table.load_factor(), 7 / 16)
        for key, value in entries:
            with self.subTest(key=key):
                self.assertEqual(table.get(key), value)

    def test_none_max_load_disables_automatic_growth(self):
        table = LinearProbingHashTable(initial_capacity=8, max_load=None)

        for index in range(8):
            table.put(f"item-{index}", index)

        self.assertEqual(len(table), 8)
        self.assertEqual(table.capacity, 8)

    def test_inserting_into_a_full_table_raises_instead_of_looping(self):
        table = LinearProbingHashTable(initial_capacity=3, max_load=None)
        table.put("first", 1)
        table.put("second", 2)
        table.put("third", 3)

        with self.assertRaises(OverflowError):
            table.put("fourth", 4)


if __name__ == "__main__":
    unittest.main()
