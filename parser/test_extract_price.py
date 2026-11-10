"""Тесты поиска цены. Запуск: python -m unittest -v"""

import unittest

from extract_price import find_prices, is_announcement


class FindPricesTest(unittest.TestCase):
    def test_narxi_uppercase(self):
        self.assertEqual(find_prices("Changan Q07 Hybrid\n\nNARXI:30.900💰"), [30900])

    def test_narxi_capitalized(self):
        self.assertEqual(find_prices("Narxi:33.300💰"), [33300])

    def test_bare_number(self):
        self.assertEqual(find_prices("➖Oqga/Qora⚪️⚫️\n\n25.500💰"), [25500])

    def test_number_without_dot(self):
        self.assertEqual(find_prices("➖Notarius✅\n\n37500💰"), [37500])

    def test_over_hundred_thousand(self):
        self.assertEqual(find_prices("NARXI:109.500💰"), [109500])

    def test_prices_by_color(self):
        text = "Narxi:⤵️\n\n⚫️⚪️-44.900💰\n🔵⚪️-44.900💰\n⚫️🟠-44.500💰"
        prices = find_prices(text)
        self.assertEqual(prices, [44900, 44500])  # одинаковые цены — один раз
        self.assertEqual(min(prices), 44500)

    def test_ignores_mileage_and_phones(self):
        text = (
            "Zeekr 001\n\nNARXI:35.200💰\n\n➖Probeg 20.000km ✅\n"
            "📞+998(87)390-00-04\n📞+998(99)111-00-04"
        )
        self.assertEqual(find_prices(text), [35200])

    def test_money_emoji_without_number(self):
        self.assertEqual(find_prices("44.000💰\n➖Xolati Ideal✅\n\nNaqd💰"), [44000])
        self.assertEqual(find_prices("➖Naxtga🤝💰\n\nNARXI:107.000💰"), [107000])

    def test_no_price(self):
        self.assertEqual(find_prices("Naqd💰"), [])


class IsAnnouncementTest(unittest.TestCase):
    def test_new_batch(self):
        text = "Yengi Partiya Moshinala Keldi😎\n\nZeekr 001 YOU OQ✅\n📞+998(99)111-00-04"
        self.assertTrue(is_announcement(text))

    def test_regular_ad(self):
        self.assertFalse(is_announcement("NARXI:30.900💰"))


if __name__ == "__main__":
    unittest.main()
