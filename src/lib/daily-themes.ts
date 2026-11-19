// Подборка дня для Telegram канала: 5 случайных машин на заданную тему и итоги темы за 30 дней
// (сколько выставили, сколько продали, какие ушли быстрее всех).
// Тем 30, это гипотезы о самых частых запросах покупателей в Узбекистане (составлены 18.11.2026,
// по спросу не проверены). Каждый день идёт следующая тема, круг замыкается за 30 дней.
// Используется во вкладке админки /admin/daily.

import { searchListings, type Listing } from "./listings";

export type DailyTheme = {
  title: string; // заголовок на картинке
  brands?: string[]; // марки, как в объявлениях
  model?: RegExp; // модель: продавцы пишут её по разному, поэтому шаблон, а не точное название
  priceFrom?: number; // USD
  priceTo?: number;
  yearFrom?: number;
  fuel?: Listing["fuel"];
};

const CHINESE = ["BYD", "Lixiang", "Zeekr", "GAC", "Leapmotor", "Voyah", "Dongfeng", "Changan", "Geely", "Jetour", "Deepal", "Hongqi"];
const PREMIUM = ["BMW", "Mercedes-Benz", "Audi", "Lexus", "Land Rover", "Porsche", "Genesis", "Zeekr", "Lixiang"];

export const DAILY_THEMES: DailyTheme[] = [
  // Порядок: день подешевле, день подороже, одна марка два дня подряд не идёт
  { title: "Cobalt до 10 000$", brands: ["Chevrolet"], model: /cobalt|kobalt/i, priceTo: 10_000 },
  { title: "Lixiang L9", brands: ["Lixiang"], model: /l9/i },
  { title: "Электромобили до 20 000$", fuel: "Электро", priceTo: 20_000 },
  { title: "BMW X5 и X7", brands: ["BMW"], model: /x5|x7/i },
  { title: "Gentra до 12 000$", brands: ["Chevrolet"], model: /gentra|jentra/i, priceTo: 12_000 },
  { title: "Zeekr 9X", brands: ["Zeekr"], model: /9x/i },
  { title: "BYD до 20 000$", brands: ["BYD"], priceTo: 20_000 },
  { title: "Mercedes до 60 000$", brands: ["Mercedes-Benz"], priceTo: 60_000 },
  { title: "Spark до 8 000$", brands: ["Chevrolet"], model: /spark/i, priceTo: 8_000 },
  { title: "Voyah Free", brands: ["Voyah"], model: /free/i },
  { title: "Kia K5", brands: ["Kia"], model: /k5/i },
  { title: "Премиум от 100 000$", brands: PREMIUM, priceFrom: 100_000 },
  { title: "Nexia до 10 000$", brands: ["Chevrolet"], model: /nexia/i, priceTo: 10_000 },
  { title: "BYD Han", brands: ["BYD"], model: /^han/i },
  { title: "GAC Aion", brands: ["GAC"], model: /aion/i },
  { title: "Toyota Camry и Land Cruiser", brands: ["Toyota"], model: /camry|land cruiser|prado/i },
  { title: "Malibu до 25 000$", brands: ["Chevrolet"], model: /malibu/i, priceTo: 25_000 },
  { title: "Lixiang L7 и L6", brands: ["Lixiang"], model: /l7|l6/i },
  { title: "Китайские до 15 000$, с 2022 года", brands: CHINESE, priceTo: 15_000, yearFrom: 2022 },
  { title: "BMW i3", brands: ["BMW"], model: /^i3/i },
  { title: "Tracker до 20 000$", brands: ["Chevrolet"], model: /tracker/i, priceTo: 20_000 },
  { title: "Zeekr 001 и 7X", brands: ["Zeekr"], model: /001|7x/i },
  { title: "BYD Chazor", brands: ["BYD"], model: /chazor/i },
  { title: "Кроссоверы Chevrolet", brands: ["Chevrolet"], model: /equinox|captiva|traverse|trailblazer/i },
  { title: "Первая машина до 7 000$", priceTo: 7_000 },
  { title: "BYD Song Plus Champion", brands: ["BYD"], model: /ch[ae]m?pion|song plus/i },
  { title: "Hyundai Sonata и Tucson", brands: ["Hyundai"], model: /sonata|tucson/i },
  { title: "Leapmotor C16 и C11", brands: ["Leapmotor"], model: /c16|c11/i },
  { title: "Onix до 15 000$", brands: ["Chevrolet"], model: /onix/i, priceTo: 15_000 },
  { title: "Kia Sportage и Seltos", brands: ["Kia"], model: /sportage|seltos/i },
];

const DAY_MS = 86_400_000;
const MIN_PRICE_SHARE = 0.4; // цена ниже 40% от медианы темы считается ошибкой разбора
// Окна: обычно месяц. Если по теме за месяц не набралось пяти машин в продаже, берём три месяца.
const WINDOWS: { days: number; label: string }[] = [
  { days: 30, label: "за 30 дней" },
  { days: 90, label: "за 90 дней" },
];

// Номер темы на день: каждый день следующая, через 30 дней круг повторяется
export function themeIndexForDay(day: string): number {
  return Math.floor(Date.parse(`${day}T00:00:00Z`) / DAY_MS) % DAILY_THEMES.length;
}

function matches(listing: Listing, theme: DailyTheme): boolean {
  return (
    (!theme.brands || theme.brands.includes(listing.brand)) &&
    (!theme.model || theme.model.test(listing.model)) &&
    (theme.priceFrom === undefined || listing.price! >= theme.priceFrom) &&
    (theme.priceTo === undefined || listing.price! <= theme.priceTo) &&
    (theme.yearFrom === undefined || (listing.year !== undefined && listing.year >= theme.yearFrom)) &&
    (!theme.fuel || listing.fuel === theme.fuel)
  );
}

// Случайные числа, которые зависят только от строки: в один день подборка одна и та же при каждом открытии
function seededRandom(seed: string) {
  let state = 2166136261;
  for (const char of seed) state = Math.imul(state ^ char.charCodeAt(0), 16777619);
  return () => {
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Итоги темы за окно: сколько выставили, сколько продали и какие машины ушли быстрее всех
export type ThemeStats = {
  listed: number; // объявлений по теме за окно, вместе с проданными
  sold: number; // из них помечены проданными
  medianPrice?: number; // USD
  medianDaysToSell?: number; // по машинам с известным сроком продажи
  fastSold: Listing[]; // проданы быстрее всех (срок известен), от самых быстрых
};

export type ThemePick = {
  theme: DailyTheme;
  index: number;
  window: string; // "за 30 дней"
  found: number; // сколько машин по теме сейчас в продаже
  listings: Listing[]; // 5 случайных из них
  stats: ThemeStats;
};

function median(values: number[]): number | undefined {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted.length ? sorted[Math.floor(sorted.length / 2)] : undefined;
}

// 5 случайных машин на тему и итоги темы за месяц.
// На картинку идут машины в наличии, с ценой в долларах и фото, не проданные, не под заказ.
// day: последний день окна ("2026-11-16"), от него считаем 30 дней назад.
export function getThemePick(index: number, day: string, limit = 5, fastLimit = 3): ThemePick {
  const theme = DAILY_THEMES[index];
  const end = Date.parse(`${day}T00:00:00Z`) + DAY_MS - 5 * 3600 * 1000; // конец дня по Ташкенту
  // Все объявления по теме, вместе с проданными: по ним считаются итоги
  const themed = searchListings().filter(
    (car) => !car.priceType && car.price !== undefined && car.currency === "USD" && car.brand && matches(car, theme),
  );
  const inWindow = (iso: string | undefined, days: number) => {
    const time = iso ? Date.parse(iso) : NaN;
    return time <= end && time > end - days * DAY_MS;
  };
  let window = WINDOWS[0];
  let all: Listing[] = [];
  let onSale: Listing[] = [];
  let floor = 0;
  for (const candidate of WINDOWS) {
    window = candidate;
    const raw = themed.filter((car) => inWindow(car.createdAt, candidate.days));
    // Цена в разы ниже обычной для темы почти всегда ошибка разбора: первый взнос рассрочки вместо цены.
    // Такие объявления не показываем и в итогах не считаем.
    floor = (median(raw.map((car) => car.price!)) ?? 0) * MIN_PRICE_SHARE;
    all = raw.filter((car) => car.price! >= floor);
    onSale = all.filter((car) => !car.isSold && car.image);
    if (onSale.length >= limit) break;
  }
  const random = seededRandom(`${day}:${index}`);
  const listings = onSale
    .map((car) => ({ car, order: random() }))
    .sort((a, b) => a.order - b.order || a.car.id.localeCompare(b.car.id))
    .slice(0, limit)
    .map((item) => item.car)
    .sort((a, b) => b.price! - a.price!); // на картинке от дорогих к дешёвым: первая плитка самая большая

  // Быстро проданные: «продано» пришло в этом окне и известен срок от первой публикации
  const soldWithTerm = themed.filter(
    (car) => car.daysToSell !== undefined && car.price! >= floor && inWindow(car.soldAt, window.days),
  );
  return {
    theme,
    index,
    window: window.label,
    found: onSale.length,
    listings,
    stats: {
      listed: all.length,
      sold: all.filter((car) => car.isSold).length,
      medianPrice: median(all.map((car) => car.price!)),
      medianDaysToSell: median(soldWithTerm.map((car) => car.daysToSell!)),
      fastSold: [...soldWithTerm].sort((a, b) => a.daysToSell! - b.daysToSell! || a.id.localeCompare(b.id)).slice(0, fastLimit),
    },
  };
}
