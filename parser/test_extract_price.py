"""Тесты поиска цены. Запуск: python -m unittest -v"""

import unittest

from extract_price import find_prices, is_announcement, main_price


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


class OtherFormatsTest(unittest.TestCase):
    """Форматы других продавцов (по постам 10.11.2026)."""

    CASES = {
        "💰 NARXI: 19 500 $": [19500],
        "💰 Цена: $31.500 Наличные!": [31500],
        "НАРХИ 💲 24.500": [24500],
        "- Narxi 111000$": [111000],
        "💸Price: 92.000y.e": [92000],
        "▪️Narxi:33.200✅": [33200],
        "💵34 500$ КЕЛИШАМИЗ": [34500],
        "💵Cтоимость 130.000$🤩": [130000],
        "CIP UZBEKISTAN: $300 000": [300000],
        "Narxi tushti 🔥 69.900 🔥": [69900],
        "💰 1.261.ml (106000$)": [106000],
        "Aion i60 530km elektr 26100$ naqd 90-9865890": [26100],
    }
    NOT_PRICES = [
        "🔥 BOSHLANG‘ICH TO‘LOV — 300$",
        "💵 Boshlang’ich to’lov: 1700$",
        "💵 Narxi: 59,000,000 won",
        "Uning narxi 1,5–2 million yuan",
        "90-317-27-78 NARXI BILAN OLAMIZ",
        "✅ 4 новые мягкие шины ($600)",
    ]

    def test_formats(self):
        for text, expected in self.CASES.items():
            with self.subTest(text=text):
                self.assertEqual(find_prices(text), expected)

    def test_not_prices(self):
        for text in self.NOT_PRICES:
            with self.subTest(text=text):
                self.assertEqual(find_prices(text), [])


class MainPriceTest(unittest.TestCase):
    def test_installment_is_not_price(self):
        # autopriceuz, BMW X6: взнос в рассрочку не должен стать ценой
        text = "Bmw X6 Xdrive 40i\n- Narxi - 27.800$\n- Nasiyaga - 10.000$ boshiga"
        self.assertEqual(main_price(text), 27800)

    def test_prices_by_color_take_min(self):
        text = "Narxi:⤵️\n\n⚫️⚪️-44.900💰\n⚫️🟠-44.500💰"
        self.assertEqual(main_price(text), 44500)

    def test_keyword_price_first(self):
        text = "💰 270 000 $ — без растаможки\nЦена: 345 000 $ с растаможкой"
        self.assertEqual(main_price(text), 345000)


if __name__ == "__main__":
    unittest.main()
