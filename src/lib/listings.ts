// Объявления, выгруженные из Instagram и Telegram (parser/export_to_site.py).
// Позже этот файл заменится запросами к базе данных,
// а остальной код почти не изменится: страницы зовут только функции ниже.

import instagramPosts from "@/data/instagram-listings.json";
import type { BODY_TYPES, DRIVES, FUEL_TYPES, TRANSMISSIONS } from "./catalog";
import { parseNumber } from "./format";

export type Currency = "UZS" | "USD";

// Площадка, с которой взято объявление
export type SourcePlatform = "instagram" | "telegram";

export const SOURCE_LABELS: Record<SourcePlatform, string> = {
  instagram: "Instagram",
  telegram: "Telegram",
};

// Цена не за машину в наличии: под заказ, с доставкой до Ташкента (CIP) или без растаможки
export type PriceType = "order" | "cip" | "no_customs";

export const PRICE_TYPE_LABELS: Record<PriceType, string> = {
  order: "Под заказ",
  cip: "Под заказ, CIP Ташкент",
  no_customs: "Без растаможки",
};

const FUELS: readonly string[] = ["Бензин", "Газ/бензин", "Дизель", "Гибрид", "Электро"];

// Тестовый курс, чтобы фильтр по цене в сумах работал и для цен в долларах
export const MARKET_LABELS = { below: "Ниже рынка", fair: "Цена в рынке", above: "Выше рынка" } as const;
export const MARKET_COLORS = { below: "text-emerald-700", fair: "text-slate-500", above: "text-rose-600" } as const;
export const LIQUIDITY_LABELS = { high: "Продаётся быстро", medium: "Продаётся средне", low: "Продаётся медленно" } as const;

export const USD_TO_UZS = 12_500;

// Поля со знаком «?» есть не у всех объявлений (например, у Instagram нет города).
export type Listing = {
  id: string;
  brand: string;
  model: string;
  title?: string; // полное название из поста: "Zeekr 001 WE 100kWh"
  year?: number;
  price?: number; // нет у объявлений «цена по запросу»
  currency: Currency;
  downPayment?: number; // первый взнос в USD, если продавец указал рассрочку
  priceType?: PriceType; // не указано = машина в наличии, цена полная
  interiorColor?: string; // цвет салона, если продавец его написал
  mileage?: number; // в километрах
  city?: string;
  bodyType?: (typeof BODY_TYPES)[number];
  engine?: string;
  fuel?: (typeof FUEL_TYPES)[number];
  transmission?: (typeof TRANSMISSIONS)[number];
  drive?: (typeof DRIVES)[number];
  color?: { name: string; hex: string };
  description: string;
  seller?: { name: string; phone: string; type: "Частное лицо" | "Автосалон" };
  image?: string; // настоящее фото: "/ig/DfhLAoxR1JB.jpg"
  source?: { account: string; url: string; platform: SourcePlatform }; // откуда взято объявление
  // Оценка по похожим машинам на сайте (считает parser/market.py)
  market?: { price: number; low: number; high: number; count: number; label: "below" | "fair" | "above" };
  liquidity?: "high" | "medium" | "low"; // как быстро продаётся эта модель, по отметкам «продано»
  alsoAt?: { account: string; url: string; price?: number }[]; // эта же машина в других каналах
  isSold?: boolean; // продавец пометил пост как проданный ("BARAKA BOLDI", "ПРОДАНО")
  createdAt: string;
};

const INSTAGRAM_LISTINGS: Listing[] = instagramPosts.map((post) => ({
  id: post.id,
  brand: post.brand ?? "",
  model: post.model ?? "",
  title: post.title ?? undefined,
  year: post.year ?? undefined,
  price: post.price ?? undefined,
  currency: "USD",
  downPayment: post.down_payment ?? undefined,
  priceType: (post.price_type as PriceType | null) ?? undefined,
  fuel: FUELS.includes(post.fuel ?? "") ? (post.fuel as Listing["fuel"]) : undefined,
  color: post.body_color ? { name: post.body_color, hex: post.body_color_hex ?? "#9ca3af" } : undefined,
  interiorColor: post.interior_color ?? undefined,
  city: post.city ?? undefined,
  market:
    post.market_price !== null && post.price_label !== null && post.price_label !== "check"
      ? {
          price: post.market_price,
          low: post.market_low ?? post.market_price,
          high: post.market_high ?? post.market_price,
          count: post.market_n ?? 0,
          label: post.price_label as "below" | "fair" | "above",
        }
      : undefined,
  liquidity: post.liquidity_level === "model" ? (post.liquidity_label as "high" | "medium" | "low") : undefined,
  alsoAt: (post.also_at as { account: string; url: string; price?: number | null }[])
    .filter((place) => place.account !== post.source_account)
    .map((place) => ({ account: place.account, url: place.url, price: place.price ?? undefined })),
  mileage: post.mileage_km ?? undefined,
  description: post.description,
  image: post.image ?? undefined,
  source: {
    account: post.source_account,
    url: post.source_url,
    platform: post.source === "telegram" ? "telegram" : "instagram",
  },
  isSold: post.is_sold,
  createdAt: post.date,
}));

const LISTINGS: Listing[] = INSTAGRAM_LISTINGS;

// "Zeekr 001 WE 100kWh, 2024" или "Chevrolet Cobalt, 2023"
export function listingTitle(listing: Listing) {
  const name = listing.title ?? `${listing.brand} ${listing.model}`;
  return listing.year ? `${name}, ${listing.year}` : name;
}

// Цена в сумах. undefined, если цена не указана («цена по запросу»).
export function priceInSum(listing: Listing) {
  if (listing.price === undefined) return undefined;
  return listing.currency === "USD" ? listing.price * USD_TO_UZS : listing.price;
}

// Марки и модели для поиска — только те, что есть в объявлениях
export function getBrandModels(): Record<string, string[]> {
  const result: Record<string, Set<string>> = {};
  const add = (brand: string, model: string) => (result[brand] ??= new Set()).add(model);
  for (const car of LISTINGS) {
    // У части постов марку или модель определить нельзя: в фильтр их не добавляем
    if (car.brand && car.model) add(car.brand, car.model);
  }

  return Object.fromEntries(
    Object.keys(result)
      .sort((a, b) => a.localeCompare(b))
      .map((brand) => [brand, [...result[brand]].sort((a, b) => a.localeCompare(b))]),
  );
}

// Популярные марки для главной: у кого больше minCount машин в продаже,
// от самых частых к редким. Если таких мало, берём первые atLeast марок.
export function getPopularBrands(minCount = 20, atLeast = 10): string[] {
  const counts: Record<string, number> = {};
  for (const car of LISTINGS) {
    if (car.brand && !car.isSold) counts[car.brand] = (counts[car.brand] ?? 0) + 1;
  }
  const sorted = Object.keys(counts).sort((a, b) => counts[b] - counts[a] || a.localeCompare(b));
  const popular = sorted.filter((brand) => counts[brand] > minCount);
  return popular.length >= atLeast ? popular : sorted.slice(0, atLeast);
}

// Сколько карточек показываем на одной странице ленты
export const PAGE_SIZE = 24;

// Что может прийти из поисковой формы (все поля необязательные).
export type ListingFilters = {
  brand?: string;
  model?: string;
  city?: string;
  priceFrom?: number;
  priceTo?: number;
  yearFrom?: number;
  yearTo?: number;
  seller?: string; // Instagram-аккаунт продавца: /cars?seller=moshinasale
  hideSold?: boolean; // не показывать проданные
  sort?: "new" | "cheap" | "expensive";
};

// Превращает параметры из адреса (?brand=Kia&priceTo=300000000) в фильтры.
export function filtersFromSearchParams(
  params: Record<string, string | string[] | undefined>,
): ListingFilters {
  const text = (key: string) => {
    const value = params[key];
    return typeof value === "string" && value.trim() ? value.trim() : undefined;
  };
  const sort = text("sort");
  return {
    brand: text("brand"),
    model: text("model"),
    city: text("city"),
    priceFrom: parseNumber(params.priceFrom),
    priceTo: parseNumber(params.priceTo),
    yearFrom: parseNumber(params.yearFrom),
    yearTo: parseNumber(params.yearTo),
    seller: text("seller"),
    hideSold: text("hideSold") === "1",
    sort: sort === "cheap" || sort === "expensive" ? sort : "new",
  };
}

// Цены сравниваются в сумах. Если задан фильтр по году или цене,
// объявления без года или без цены не показываются — их значение неизвестно.
export function searchListings(filters: ListingFilters = {}): Listing[] {
  const priceAtLeast = (car: Listing, min: number) => (priceInSum(car) ?? -Infinity) >= min;
  const priceAtMost = (car: Listing, max: number) => (priceInSum(car) ?? Infinity) <= max;
  const found = LISTINGS.filter(
    (car) =>
      (!filters.brand || car.brand === filters.brand) &&
      (!filters.model || car.model === filters.model) &&
      (!filters.city || car.city === filters.city) &&
      (!filters.seller || car.source?.account === filters.seller) &&
      (!filters.hideSold || !car.isSold) &&
      (filters.priceFrom === undefined || priceAtLeast(car, filters.priceFrom)) &&
      (filters.priceTo === undefined || priceAtMost(car, filters.priceTo)) &&
      (filters.yearFrom === undefined || (car.year !== undefined && car.year >= filters.yearFrom)) &&
      (filters.yearTo === undefined || (car.year !== undefined && car.year <= filters.yearTo)),
  );

  return found.sort((a, b) => {
    // Проданные всегда в конце списка, при любой сортировке
    if (Boolean(a.isSold) !== Boolean(b.isSold)) return a.isSold ? 1 : -1;
    // При сортировке по цене объявления без цены идут в конце
    if (filters.sort === "cheap") return (priceInSum(a) ?? Infinity) - (priceInSum(b) ?? Infinity);
    if (filters.sort === "expensive") return (priceInSum(b) ?? -Infinity) - (priceInSum(a) ?? -Infinity);
    return b.createdAt.localeCompare(a.createdAt);
  });
}

// Сколько машин сейчас в продаже (проданные не считаем)
export function countActiveListings(): number {
  return LISTINGS.filter((car) => !car.isSold).length;
}

// Сколько объявлений у продавца (для ссылки "Все объявления продавца")
export function countSellerListings(account: string): number {
  return LISTINGS.filter((car) => car.source?.account === account).length;
}

// Похожие объявления: та же марка и модель, год не дальше SIMILAR_YEARS, ближе по году и пробегу идут первыми.
// Проданные не показываем. Машины под заказ показываем только к машине под заказ.
const SIMILAR_YEARS = 2;
const SIMILAR_KM_PER_YEAR = 30_000; // разница в год весит как 30 000 км пробега

export function getSimilarListings(listing: Listing, limit = 4): Listing[] {
  if (!listing.brand || !listing.model) return [];
  const brand = listing.brand.toLowerCase();
  const model = listing.model.toLowerCase();
  const distance = (car: Listing) => {
    const years = listing.year !== undefined && car.year !== undefined ? Math.abs(car.year - listing.year) : SIMILAR_YEARS;
    const km =
      listing.mileage !== undefined && car.mileage !== undefined
        ? Math.abs(car.mileage - listing.mileage)
        : SIMILAR_KM_PER_YEAR;
    return years * SIMILAR_KM_PER_YEAR + km;
  };
  return LISTINGS.filter(
    (car) =>
      car.id !== listing.id &&
      !car.isSold &&
      car.brand.toLowerCase() === brand &&
      car.model.toLowerCase() === model &&
      Boolean(car.priceType) === Boolean(listing.priceType) &&
      (listing.year === undefined || car.year === undefined || Math.abs(car.year - listing.year) <= SIMILAR_YEARS),
  )
    .sort((a, b) => distance(a) - distance(b))
    .slice(0, limit);
}

export function getListing(id: string): Listing | undefined {
  return LISTINGS.find((car) => car.id === id);
}

export function getAllListingIds(): string[] {
  return LISTINGS.map((car) => car.id);
}
