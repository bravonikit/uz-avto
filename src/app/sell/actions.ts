"use server";
// "use server" значит: эти функции выполняются только на сервере.
// Браузер присылает сюда данные формы, а мы их проверяем.

import { BRANDS, CITIES, NEWEST_YEAR, OLDEST_YEAR } from "@/lib/catalog";
import { parseNumber } from "@/lib/format";

export type SellFormState = {
  status: "idle" | "error" | "success";
  errors?: Partial<Record<string, string>>;
  values?: Record<string, string>; // чтобы при ошибке поля не очищались
  summary?: string;
};

export async function submitListing(
  _prevState: SellFormState,
  formData: FormData,
): Promise<SellFormState> {
  const values: Record<string, string> = {};
  for (const [key, value] of formData) {
    if (typeof value === "string" && !key.startsWith("$ACTION")) values[key] = value.trim();
  }

  const errors: Record<string, string> = {};
  const year = parseNumber(values.year);
  const price = parseNumber(values.price);
  const mileage = parseNumber(values.mileage);
  const phoneDigits = (values.phone ?? "").replace(/\D/g, "");

  if (!values.brand || !BRANDS[values.brand]) errors.brand = "Выберите марку";
  else if (!BRANDS[values.brand].includes(values.model)) errors.model = "Выберите модель";
  if (!year || year < OLDEST_YEAR || year > NEWEST_YEAR) errors.year = "Укажите год";
  if (!price || price < 1_000_000) errors.price = "Укажите цену в сумах (от 1 000 000)";
  if (mileage === undefined) errors.mileage = "Укажите пробег (0 — если новая)";
  if (!CITIES.includes(values.city)) errors.city = "Выберите город";
  if (!values.name) errors.name = "Как к вам обращаться?";
  // Узбекский номер: 998 + 9 цифр
  if (!/^998\d{9}$/.test(phoneDigits)) errors.phone = "Формат: +998 90 123-45-67";

  if (Object.keys(errors).length > 0) {
    return { status: "error", errors, values };
  }

  // TODO: когда подключим базу данных — сохранять объявление здесь.
  return {
    status: "success",
    summary: `${values.brand} ${values.model}, ${year} · ${new Intl.NumberFormat("ru-RU").format(price!)} сум · ${values.city}`,
  };
}
