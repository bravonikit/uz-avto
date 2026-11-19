"""Тесты запаса хода (ev_specs.py), перевода цен (card_fields.py) и поправки на пробег (market_adjust.py)."""
import unittest

from card_fields import _to_usd
from ev_specs import ev_specs
from market_adjust import adjusted, fit_slopes


class EvSpecsTest(unittest.TestCase):
    def test_range_in_name_and_explicit(self):
        self.assertEqual(ev_specs("BYD", "Song Plus", "Byd Champion 605 Full", "▪️2024 йил ▪️18.000 км")["range_km"], 605)
        self.assertEqual(ev_specs("Zeekr", "007", "Zeekr 007", "▪️Lidarliy zapas hod 788 ▪️")["range_km"], 788)
        self.assertEqual(ev_specs("BYD", "Han", "BYD Xan", "🔋550 km 2021 yil. 97.000 km.")["range_km"], 550)

    def test_battery_and_now(self):
        specs = ev_specs("Leapmotor", "C11", "Leapmotor C11", "LEAPMOTOR C11 ev580 93%🔋 токда 450 км юради")
        self.assertEqual((specs["range_km"], specs["battery_pct"], specs["range_now_km"]), (580, 93, 450))

    def test_hybrid_total_range(self):
        specs = ev_specs("BYD", "Song Plus", "Byd Champion Hybrid 1250 km", "гибрид")
        self.assertEqual(specs.get("range_total_km"), 1250)
        self.assertNotIn("range_km", specs)

    def test_not_phone_price_power_or_model_number(self):
        self.assertNotIn("range_km", ev_specs("BYD", "Han", "BYD Han", "📞(95)605-70-77 ▪️19.900$ ▪️340 ot kuchi"))
        self.assertNotIn("range_km", ev_specs("Lynk & Co", "900", "Lynk & Co 900", "2025"))
        self.assertEqual(ev_specs("Chevrolet", "Malibu 2", "Malibu 2", "2021 107.000km"), {})


class PriceTest(unittest.TestCase):
    def test_to_usd(self):
        self.assertEqual(_to_usd(19.9, "USD"), 19900)
        self.assertEqual(_to_usd(250_000_000, "UZS"), 20000)
        self.assertIsNone(_to_usd("нет", "USD"))


class MileageTest(unittest.TestCase):
    def test_higher_mileage_analog_gets_more_expensive_for_low_mileage_car(self):
        cars = [{"price": 20000 - km // 10, "year": 2021, "mileage_km": km} for km in range(10_000, 150_000, 10_000)]
        slopes, general = fit_slopes({("a", "b"): cars})
        slope = slopes[("a", "b")]
        self.assertLess(slope[1], 0)
        analog = {"year": 2021, "mileage_km": 140_000}
        target = {"year": 2021, "mileage_km": 20_000}
        self.assertGreater(adjusted(15000, analog, target, slope), 15000)


if __name__ == "__main__":
    unittest.main()
