"""Тесты фильтра странных цен. Запуск: python -m unittest -v"""

import unittest

from export_to_site import find_price_suspects


def car(id: str, price: int | None, year: int | None = 2024, account: str | None = None) -> dict:
    return {
        "id": id, "brand": "BMW", "model": "X7", "year": year, "price": price,
        "source_account": account or f"shop_{id}",
    }


class PriceSuspectsTest(unittest.TestCase):
    def test_far_below_analogs(self):
        # 30 000$ при аналогах по 74-80 тысяч: похоже на взнос или цену в рассрочку
        cars = [car("a", 30_000), car("b", 73_900), car("c", 79_900), car("d", 76_000)]
        self.assertEqual(list(find_price_suspects(cars, set())), ["a"])

    def test_far_above_analogs(self):
        cars = [car("a", 180_000), car("b", 73_900), car("c", 79_900)]
        self.assertEqual(list(find_price_suspects(cars, set())), ["a"])

    def test_normal_spread_is_fine(self):
        cars = [car("a", 62_000), car("b", 73_900), car("c", 79_900)]
        self.assertEqual(find_price_suspects(cars, set()), {})

    def test_other_years_are_not_analogs(self):
        # Машина 2012 года законно стоит в разы дешевле машин 2024 года
        cars = [car("a", 20_000, year=2012), car("b", 73_900), car("c", 79_900)]
        self.assertEqual(find_price_suspects(cars, set()), {})

    def test_too_cheap_for_recent_car(self):
        cars = [car("a", 1_500, year=2025)]
        self.assertEqual(list(find_price_suspects(cars, set())), ["a"])

    def test_old_cheap_car_is_fine(self):
        self.assertEqual(find_price_suspects([car("a", 1_500, year=2009)], set()), {})

    def test_manually_checked_price_is_skipped(self):
        cars = [car("a", 1_500, year=2025)]
        self.assertEqual(find_price_suspects(cars, {"a"}), {})

    def test_no_price_is_skipped(self):
        cars = [car("a", None), car("b", 73_900), car("c", 79_900)]
        self.assertEqual(find_price_suspects(cars, set()), {})


if __name__ == "__main__":
    unittest.main()
