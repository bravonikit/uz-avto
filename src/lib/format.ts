// Функции, которые превращают числа и даты в красивый текст.

const numberFormat = new Intl.NumberFormat("ru-RU");

// 155000000 → "155 000 000 сум", 35200 в USD → "$35 200"
export function formatPrice(amount: number, currency: "UZS" | "USD" = "UZS") {
  return currency === "USD"
    ? `$${numberFormat.format(amount)}`
    : `${numberFormat.format(amount)} сум`;
}

// 35000 → "35 000 км"
export function formatMileage(km: number) {
  return km === 0 ? "Новый" : `${numberFormat.format(km)} км`;
}

const dateFormat = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "long",
  timeZone: "Asia/Tashkent",
});

// "2026-11-08" → "8 ноября"
export function formatDate(isoDate: string) {
  return dateFormat.format(new Date(isoDate));
}

// "150 000 000" или "150000000" → 150000000. Пустая строка → undefined.
export function parseNumber(value: unknown) {
  if (typeof value !== "string") return undefined;
  const digits = value.replace(/\D/g, "");
  return digits ? Number(digits) : undefined;
}
