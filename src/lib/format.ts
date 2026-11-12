// Функции, которые превращают числа и даты в красивый текст.

const numberFormat = new Intl.NumberFormat("ru-RU");

// 155000000 → "155 000 000 сум", 35200 в USD → "$35 200", нет цены → "Цена по запросу"
export function formatPrice(amount: number | undefined, currency: "UZS" | "USD" = "UZS") {
  if (amount === undefined) return "Цена по запросу";
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

// День по ташкентскому времени: "2026-11-11"
const dayFormat = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Tashkent" });

// Сегодняшний пост → "сегодня", вчерашний → "вчера", до недели → "3 дня назад", старше → "8 ноября"
export function formatFreshness(isoDate: string, now: Date = new Date()) {
  const day = (date: Date) => Date.parse(dayFormat.format(date));
  const daysAgo = Math.round((day(now) - day(new Date(isoDate))) / 86_400_000);
  if (daysAgo <= 0) return "сегодня";
  if (daysAgo === 1) return "вчера";
  if (daysAgo <= 4) return `${daysAgo} дня назад`;
  if (daysAgo <= 6) return `${daysAgo} дней назад`;
  return formatDate(isoDate);
}

// "150 000 000" или "150000000" → 150000000. Пустая строка → undefined.
export function parseNumber(value: unknown) {
  if (typeof value !== "string") return undefined;
  const digits = value.replace(/\D/g, "");
  return digits ? Number(digits) : undefined;
}
