import unittest

from src.hash_table import HashTable


class HashTableTests(unittest.TestCase):
    def test_horner_hash_trace_records_each_character_step(self):
        table = HashTable()

        bucket_index, steps = table.hash_trace("abc", capacity=8)

        self.assertEqual(bucket_index, 2)
        self.assertEqual(
            [
                (
                    step.character,
                    step.codepoint,
                    step.previous_hash,
                    step.current_hash,
                )
                for step in steps
            ],
            [
                ("a", ord("a"), 0, 1),
                ("b", ord("b"), 1, 1),
                ("c", ord("c"), 1, 2),
            ],
        )
        self.assertEqual(table.hash_index("abc"), 2)

    def test_separate_chaining_keeps_colliding_keys(self):
        table = HashTable(initial_capacity=8, max_load=None)

        # "a" and "i" both hash to bucket 1 at capacity 8.
        self.assertEqual(table.hash_index("a"), table.hash_index("i"))
        table.put("a", "first")
        table.put("i", "second")

        self.assertEqual(table.get("a"), "first")
        self.assertEqual(table.get("i"), "second")
        self.assertCountEqual(
            [key for key, _value in table.bucket_items(table.hash_index("a"))],
            ["a", "i"],
        )

    def test_empty_lookup_and_updating_existing_key(self):
        table = HashTable()

        self.assertEqual(len(table), 0)
        self.assertIsNone(table.get("missing"))

        table.put("same", "before")
        table.put("same", "after")

        self.assertEqual(table.get("same"), "after")
        self.assertEqual(len(table), 1)

    def test_automatic_growth_rehashes_and_preserves_entries(self):
        table = HashTable()
        entries = [(f"item-{index}", index) for index in range(7)]

        for key, value in entries:
            table.put(key, value)

        self.assertAlmostEqual(table.load_factor(), 7 / 16)
        for key, value in entries:
            with self.subTest(key=key):
                self.assertEqual(table.get(key), value)

    def test_none_max_load_disables_automatic_growth(self):
        table = HashTable(initial_capacity=8, max_load=None)

        for index in range(10):
            table.put(f"item-{index}", index)

        self.assertEqual(len(table), 10)
        self.assertAlmostEqual(table.load_factor(), 10 / 8)

    def test_lookup_comparison_counts_for_success_and_failure(self):
        table = HashTable(initial_capacity=8, max_load=None)
        table.put("a", "first")
        table.put("i", "second")

        first_value, first_comparisons = table.get_with_comparisons("a")
        second_value, second_comparisons = table.get_with_comparisons("i")
        missing_value, failed_comparisons = table.get_with_comparisons("q")

        self.assertEqual(first_value, "first")
        self.assertEqual(second_value, "second")
        self.assertEqual(first_comparisons + second_comparisons, 3)
        self.assertIsNone(missing_value)
        self.assertEqual(failed_comparisons, 2)


if __name__ == "__main__":
    unittest.main()
