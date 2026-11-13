"""Тесты дополнительных полей. Запуск: python -m unittest -v"""

import unittest

from enrich import find_city, find_colors, find_fuel, find_price_type


def names(pair):
    return tuple(color[0] if color else None for color in pair)


class PriceTypeTest(unittest.TestCase):
    def test_types(self):
        self.assertEqual(find_price_type("CIP tashkent 19.400 💵"), "cip")
        self.assertEqual(find_price_type("💰 142 000 $ — без растаможки"), "no_customs")
        self.assertEqual(find_price_type("(Растаможка: примерно $7100)"), "no_customs")
        self.assertEqual(find_price_type("ПРЕДЗАКАЗ НА НОВУЮ МОДЕЛЬ"), "order")
        self.assertEqual(find_price_type("Buyurtma asosida xitoydan"), "order")

    def test_in_stock(self):
        self.assertIsNone(find_price_type("Narxi: 15.000$"))
        self.assertIsNone(find_price_type("Rastamojka qilingan."))
        self.assertIsNone(find_price_type("Привезена с Кореи на заказ в 2026 году"))
        self.assertIsNone(find_price_type("Batafsil ma’lumot va buyurtma uchun Direct’ga yozing"))


class FuelTest(unittest.TestCase):
    def test_fuel(self):
        self.assertEqual(find_fuel("⛽ Yoqilg‘i: Benzin"), "Бензин")
        self.assertEqual(find_fuel("Aion i60 elektr 530km"), "Электро")
        self.assertEqual(find_fuel("NIO ET5 EV 585 KM"), "Электро")
        self.assertEqual(find_fuel("DM гибрид 110 км ЕV"), "Гибрид")
        self.assertEqual(find_fuel("🔹 Metan gazi bor"), "Газ/бензин")
        self.assertEqual(find_fuel("Vito 2 turbodizel"), "Дизель")

    def test_not_fuel(self):
        self.assertIsNone(find_fuel("▪️9D Gibrid Polik"))
        self.assertIsNone(find_fuel("narsasi elektronikasi ishlidi"))
        self.assertIsNone(find_fuel("- электрические пороги"))
        self.assertIsNone(find_fuel("Elektromator: 3 ta"))


class ColorsTest(unittest.TestCase):
    def test_colors(self):
        self.assertEqual(names(find_colors("🩸Rangi oq")), ("белый", None))
        self.assertEqual(names(find_colors("Oqga qora salon")), ("белый", "чёрный"))
        self.assertEqual(names(find_colors("▪️Цвет: окга кора")), ("белый", "чёрный"))
        self.assertEqual(names(find_colors("▪️Rangi Mokriy Asfalt ga Qora salon")), ("мокрый асфальт", "чёрный"))
        self.assertEqual(names(find_colors("🎨 Цвет: Кузов: Белый / Салон: Бордовый")), ("белый", "бордовый"))
        self.assertEqual(names(find_colors("▪️Кузов : чёрный\n▪️салон : кофейный")), ("чёрный", "коричневый"))
        self.assertEqual(names(find_colors("• Oqga Parlament салон")), ("белый", None))
        self.assertEqual(names(find_colors("Холати зур серый салон")), (None, "серый"))

    def test_no_marker_no_color(self):
        self.assertEqual(names(find_colors("Qora diskalar, oq fara")), (None, None))


class CityTest(unittest.TestCase):
    def test_city(self):
        self.assertEqual(find_city("📍Viloyat Samarqand"), "Самарканд")
        self.assertEqual(find_city("Манзил: Наманган шахар"), "Наманган")

    def test_not_city(self):
        self.assertIsNone(find_city("CIP Tashkent - 175 000 $"))
        self.assertIsNone(find_city("📍 Toshkent shahar propiskaga beriladi"))
        self.assertIsNone(find_city("12Ta Viloyatga Beriladi"))


if __name__ == "__main__":
    unittest.main()
