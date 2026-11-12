"""Тесты склейки дублей внутри аккаунта. Запуск: python -m unittest -v"""

import unittest

from export_to_site import merge_account_duplicates


def car(id: str, date: str, **fields) -> dict:
    base = {
        "id": id, "source_account": "shop", "brand": "Zeekr", "model": "001", "year": 2024,
        "mileage_km": 20_000, "price": 35_000, "currency": "USD", "down_payment": None,
        "image": f"/ig/{id}.jpg", "is_sold": False, "date": date,
        "description": f"Zeekr 001, пост {id}, год 2024, пробег 20 000",
    }
    return base | fields


def ids(listings: list[dict]) -> list[str]:
    return [item["id"] for item in listings]


class MergeDuplicatesTest(unittest.TestCase):
    def test_same_used_car_keeps_freshest(self):
        cars = [car("old", "2026-11-05T10:00:00Z", price=36_200), car("new", "2026-11-08T10:00:00Z", price=35_200)]
        kept, removed = merge_account_duplicates(cars)
        self.assertEqual((ids(kept), removed), (["new"], 1))
        self.assertEqual(kept[0]["price"], 35_200)
        self.assertEqual(kept[0]["duplicate_ids"], ["old"])

    def test_other_account_is_not_merged(self):
        cars = [car("a", "2026-11-05T10:00:00Z"), car("b", "2026-11-08T10:00:00Z", source_account="other")]
        self.assertEqual(merge_account_duplicates(cars)[1], 0)

    def test_sold_mark_is_kept(self):
        cars = [car("sold", "2026-11-05T10:00:00Z", is_sold=True), car("new", "2026-11-05T11:00:00Z")]
        kept, _ = merge_account_duplicates(cars)
        self.assertEqual(ids(kept), ["new"])
        self.assertTrue(kept[0]["is_sold"])

    def test_missing_price_comes_from_older_post(self):
        cars = [car("old", "2026-11-05T10:00:00Z", price=36_200), car("new", "2026-11-08T10:00:00Z", price=None)]
        kept, _ = merge_account_duplicates(cars)
        self.assertEqual(kept[0]["price"], 36_200)

    def test_new_cars_with_different_text_stay(self):
        # У салона могут стоять две одинаковые новые машины разного цвета
        cars = [car("a", "2026-11-05T10:00:00Z", mileage_km=0), car("b", "2026-11-08T10:00:00Z", mileage_km=0)]
        self.assertEqual(merge_account_duplicates(cars)[1], 0)

    def test_same_text_is_merged_even_for_new_cars(self):
        text = "Gac Aion S Plus Narxi : 23.550 Yili : 2026 Probeg :0"
        cars = [
            car("a", "2026-11-05T10:00:00Z", mileage_km=0, description=text),
            car("b", "2026-11-08T10:00:00Z", mileage_km=0, description="🔥 " + text + " #gac"),
        ]
        self.assertEqual(merge_account_duplicates(cars)[1], 1)

    def test_two_posts_in_a_row_with_different_price_are_two_cars(self):
        # avenue_motors: два GLE 53 2023 с пробегом 25 000 за 95 000$ и 99 000$, выложены подряд
        cars = [car("a", "2026-11-11T10:00:00Z", price=95_000), car("b", "2026-11-11T10:20:00Z", price=99_000)]
        self.assertEqual(merge_account_duplicates(cars)[1], 0)

    def test_short_same_text_is_not_enough(self):
        cars = [
            car("a", "2026-11-05T10:00:00Z", mileage_km=None, description="Malibu 2025"),
            car("b", "2026-11-08T10:00:00Z", mileage_km=None, description="Malibu 2025"),
        ]
        self.assertEqual(merge_account_duplicates(cars)[1], 0)


if __name__ == "__main__":
    unittest.main()
