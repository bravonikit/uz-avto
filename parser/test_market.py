"""Проверка оценки цены, ликвидности и склейки одной машины у разных продавцов. Запуск: python3 test_market.py"""

import unittest
from datetime import datetime, timedelta, timezone

import export_to_site
from market import add_liquidity, add_market, add_prices


def car(number: int, price: int | None, seller: str, **extra) -> dict:
    item = {
        "id": f"car-{number}", "brand": "Chevrolet", "model": "Cobalt", "year": 2022, "mileage_km": 50_000,
        "price": price, "price_type": None, "seller_id": seller, "posted_by": seller, "source_account": seller,
        "source": "telegram", "source_url": f"https://t.me/{seller}/{number}", "is_sold": False,
        "date": "2026-11-01T10:00:00Z", "first_posted": "2026-11-01T10:00:00Z", "description": f"Cobalt номер {number}",
        "phones": [], "duplicate_ids": [], "also_at": [], "currency": "USD", "down_payment": None, "image": None,
    }
    item.update(extra)
    return item


class PriceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cars = [car(n, 12_000 + n * 100, f"seller{n}") for n in range(6)]

    def test_labels(self) -> None:
        cheap, costly, wrong = car(10, 10_500, "a"), car(11, 13_900, "b"), car(12, 5_000, "c")
        cars = self.cars + [cheap, costly, wrong]
        add_market(cars)
        self.assertEqual(cheap["price_label"], "below")
        self.assertEqual(costly["price_label"], "above")
        self.assertEqual(wrong["price_label"], "check")  # слишком далеко от рынка: похоже на ошибку
        self.assertEqual(self.cars[3]["price_label"], "fair")

    def test_own_cars_are_not_analogs(self) -> None:
        cars = [car(n, 12_000, "one") for n in range(8)]
        add_market(cars)
        self.assertIsNone(cars[0]["market_price"])

    def test_new_and_used_are_separate(self) -> None:
        new = car(20, 15_000, "z", mileage_km=0)
        cars = self.cars + [new]
        add_market(cars)
        self.assertIsNone(new["market_price"])

    def test_on_order_is_skipped(self) -> None:
        order = car(21, 9_000, "z", price_type="order")
        cars = self.cars + [order]
        for item in cars:
            item["market_price"] = None
        add_prices(cars, 2026)
        self.assertIsNone(order["market_price"])


class LiquidityTest(unittest.TestCase):
    def test_share_of_sold(self) -> None:
        now = datetime(2026, 11, 13, tzinfo=timezone.utc)
        old = (now - timedelta(days=40)).strftime("%Y-%m-%dT%H:%M:%SZ")
        cars = [car(n, 12_000, "shop", first_posted=old, is_sold=n < 6) for n in range(10)]
        fresh = car(50, 12_000, "other")
        cars.append(fresh)
        for item in cars:
            item.update(liquidity_share=None, liquidity_n=None, liquidity_label=None, liquidity_level=None)
        add_liquidity(cars, now)
        self.assertEqual((fresh["liquidity_share"], fresh["liquidity_n"], fresh["liquidity_label"]), (0.6, 10, "high"))
        self.assertEqual(fresh["liquidity_level"], "model")


class CrossSellerTest(unittest.TestCase):
    def merge(self, cars: list[dict]):
        export_to_site.CROSS_SELLER_CANDIDATES_FILE = export_to_site.PARSER_DIR / "data" / "_test_candidates.json"
        return export_to_site.merge_across_sellers(cars)

    def test_same_phone_is_merged_and_seller_post_wins(self) -> None:
        repost = car(1, 12_500, "shop", posted_by="aggregator", source_account="aggregator", phones=["998901234567"],
                     first_posted="2026-10-20T10:00:00Z")
        own = car(2, 12_000, "shop", phones=["998901234567"])
        cars, removed, candidates = self.merge([repost, own])
        self.assertEqual((len(cars), removed, candidates), (1, 1, []))
        self.assertEqual(cars[0]["id"], "car-2")
        self.assertEqual(cars[0]["also_at"][0]["price"], 12_500)
        self.assertEqual(cars[0]["first_posted"], "2026-10-20T10:00:00Z")

    def test_without_proof_only_candidate(self) -> None:
        cars, removed, candidates = self.merge([car(1, 12_000, "one"), car(2, 12_300, "two")])
        self.assertEqual((len(cars), removed, len(candidates)), (2, 0, 1))

    def test_different_mileage_is_another_car(self) -> None:
        cars, removed, candidates = self.merge([car(1, 12_000, "one"), car(2, 12_000, "two", mileage_km=70_000)])
        self.assertEqual((len(cars), removed, candidates), (2, 0, []))


if __name__ == "__main__":
    unittest.main()
