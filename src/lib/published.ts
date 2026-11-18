// Объявления продавцов из кабинета в том же виде, что и собранные из Telegram и Instagram,
// чтобы лента и страница машины показывали их одинаково.
// На сайт попадают только одобренные в админке (/admin).

import type { BODY_TYPES, DRIVES, FUEL_TYPES, TRANSMISSIONS } from "./catalog";
import { getListing, type Listing } from "./listings";
import { getPublishedSellerListings, sellerPhotoUrl, type SellerListing } from "./seller-listings";

// 998901234567 → "+998 90 123 45 67"
export function formatPhone(digits: string) {
  const match = /^998(\d{2})(\d{3})(\d{2})(\d{2})$/.exec(digits);
  return match ? `+998 ${match[1]} ${match[2]} ${match[3]} ${match[4]}` : `+${digits}`;
}

export function toListing(item: SellerListing): Listing {
  const photos = item.photos.map((file) => sellerPhotoUrl(item.id, file));
  return {
    id: item.id,
    brand: item.brand,
    model: item.model,
    year: item.year,
    price: item.price,
    currency: item.currency,
    mileage: item.mileage,
    city: item.city,
    // Значения проверены при подаче: они из тех же списков catalog.ts
    bodyType: item.bodyType as (typeof BODY_TYPES)[number] | undefined,
    fuel: item.fuel as (typeof FUEL_TYPES)[number] | undefined,
    transmission: item.transmission as (typeof TRANSMISSIONS)[number] | undefined,
    drive: item.drive as (typeof DRIVES)[number] | undefined,
    color: item.color ? { name: item.color, hex: "#9ca3af" } : undefined,
    description: item.description,
    seller: { name: item.name, phone: formatPhone(item.phone), type: "Частное лицо" },
    image: photos[0],
    photos,
    photoQuality: "good", // продавец сам загрузил фото в форму
    isSold: item.status === "sold",
    createdAt: item.publishedAt ?? item.createdAt,
  };
}

// Опубликованные объявления продавцов для ленты
export async function getPublishedListings(): Promise<Listing[]> {
  return (await getPublishedSellerListings()).map(toListing);
}

// Объявление по номеру: собранное или поданное продавцом (у таких номер начинается с "s-")
export async function findListing(id: string): Promise<Listing | undefined> {
  if (!id.startsWith("s-")) return getListing(id);
  return (await getPublishedListings()).find((listing) => listing.id === id);
}
