// Объявления, выгруженные из Instagram (parser/export_to_site.py).
// Позже этот файл заменится запросами к базе данных,
// а остальной код почти не изменится: страницы зовут только функции ниже.

import instagramPosts from "@/data/instagram-listings.json";
import type { BODY_TYPES, DRIVES, FUEL_TYPES, TRANSMISSIONS } from "./catalog";
import { parseNumber } from "./format";

export type Currency = "UZS" | "USD";

// Тестовый курс, чтобы фильтр по цене в сумах работал и для цен в долларах
export const USD_TO_UZS = 12_500;

// Поля со знаком «?» есть не у всех объявлений (например, у Instagram нет города).
export type Listing = {
  id: string;
  brand: string;
  model: string;
  title?: string; // полное название из поста: "Zeekr 001 WE 100kWh"
  year?: number;
  price: number;
  currency: Currency;
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
  source?: { account: string; url: string }; // откуда взято объявление
  createdAt: string;
};

const INSTAGRAM_LISTINGS: Listing[] = instagramPosts.map((post) => ({
  id: post.id,
  brand: post.brand ?? "",
  model: post.model ?? "",
  title: post.title ?? undefined,
  year: post.year ?? undefined,
  price: post.price,
  currency: "USD",
  mileage: post.mileage_km ?? undefined,
  description: post.description,
  image: post.image ?? undefined,
  source: { account: post.source_account, url: post.source_url },
  createdAt: post.date,
}));

const LISTINGS: Listing[] = INSTAGRAM_LISTINGS;

// "Zeekr 001 WE 100kWh, 2024" или "Chevrolet Cobalt, 2023"
export function listingTitle(listing: Listing) {
  const name = listing.title ?? `${listing.brand} ${listing.model}`;
  return listing.year ? `${name}, ${listing.year}` : name;
}

export function priceInSum(listing: Listing) {
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

// Что может прийти из поисковой формы (все поля необязательные).
export type ListingFilters = {
  brand?: string;
  model?: string;
  city?: string;
  priceFrom?: number;
  priceTo?: number;
  yearFrom?: number;
  yearTo?: number;
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
    sort: sort === "cheap" || sort === "expensive" ? sort : "new",
  };
}

// Цены сравниваются в сумах. Если задан фильтр по году,
// объявления без года не показываются — их год неизвестен.
export function searchListings(filters: ListingFilters = {}): Listing[] {
  const found = LISTINGS.filter(
    (car) =>
      (!filters.brand || car.brand === filters.brand) &&
      (!filters.model || car.model === filters.model) &&
      (!filters.city || car.city === filters.city) &&
      (filters.priceFrom === undefined || priceInSum(car) >= filters.priceFrom) &&
      (filters.priceTo === undefined || priceInSum(car) <= filters.priceTo) &&
      (filters.yearFrom === undefined || (car.year !== undefined && car.year >= filters.yearFrom)) &&
      (filters.yearTo === undefined || (car.year !== undefined && car.year <= filters.yearTo)),
  );

  return found.sort((a, b) => {
    if (filters.sort === "cheap") return priceInSum(a) - priceInSum(b);
    if (filters.sort === "expensive") return priceInSum(b) - priceInSum(a);
    return b.createdAt.localeCompare(a.createdAt);
  });
}

export function getListing(id: string): Listing | undefined {
  return LISTINGS.find((car) => car.id === id);
}

export function getAllListingIds(): string[] {
  return LISTINGS.map((car) => car.id);
}
