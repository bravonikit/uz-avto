// Объявления, которые продавцы подали сами через кабинет.
// Пока базы данных нет, всё лежит в папке .data на компьютере, где запущен сайт (в git она не попадает):
//   .data/seller-listings.json       список объявлений
//   .data/uploads/<id объявления>/   фото: 1.jpg, 2.jpg, ...
// Когда появится база, поменяется только этот файл.

import { randomBytes } from "node:crypto";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import type { Currency } from "./listings";

const DIR = path.join(process.cwd(), ".data");
const FILE = path.join(DIR, "seller-listings.json");
const UPLOADS = path.join(DIR, "uploads");

export const MAX_PHOTOS = 20;
export const MAX_PHOTO_BYTES = 5 * 1024 * 1024; // браузер сжимает фото перед отправкой, 5 МБ это запас

// moderation: подано и ждёт проверки, на сайте ещё не показывается
// active: проверено в админке (/admin) и показывается в ленте
// rejected: отклонено, продавец видит причину в кабинете
// sold: было опубликовано, машина продана
export type SellerListingStatus = "moderation" | "active" | "rejected" | "sold";

export const STATUS_LABELS: Record<SellerListingStatus, string> = {
  moderation: "На проверке",
  active: "Опубликовано",
  rejected: "Отклонено",
  sold: "Продано",
};

// То, что продавец заполнил в форме
export type SellerListingInput = {
  brand: string;
  model: string;
  year: number;
  mileage: number; // в километрах, 0 у новой машины
  price: number;
  currency: Currency;
  city: string;
  bodyType?: string;
  fuel?: string;
  transmission?: string;
  drive?: string;
  color?: string;
  description: string;
  name: string;
  phone: string; // только цифры: 998901234567
  telegram?: string; // без @
};

export type SellerListing = SellerListingInput & {
  id: string;
  sellerId: string; // кто подал: номер из куки браузера (src/lib/seller-session.ts)
  status: SellerListingStatus;
  photos: string[]; // имена файлов по порядку, первое это обложка
  createdAt: string;
  publishedAt?: string; // когда объявление одобрили в админке
  rejectReason?: string; // что написали продавцу при отказе
};

async function load(): Promise<SellerListing[]> {
  try {
    const saved: unknown = JSON.parse(await readFile(FILE, "utf8"));
    return Array.isArray(saved) ? (saved as SellerListing[]) : [];
  } catch {
    return []; // файла ещё нет: объявлений пока не подавали
  }
}

async function save(listings: SellerListing[]) {
  await mkdir(DIR, { recursive: true });
  await writeFile(FILE, JSON.stringify(listings, null, 2));
}

// Изменения делаем по очереди, чтобы два продавца одновременно не затёрли друг друга
let queue: Promise<unknown> = Promise.resolve();

function inQueue<T>(task: () => Promise<T>): Promise<T> {
  const result = queue.then(task);
  queue = result.catch(() => undefined);
  return result;
}

// Объявления одного продавца, свежие первыми
export async function getSellerListings(sellerId: string): Promise<SellerListing[]> {
  const listings = await load();
  return listings
    .filter((listing) => listing.sellerId === sellerId)
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

// Сохраняет новое объявление и его фото. Объявление попадает на проверку.
export function addSellerListing(
  sellerId: string,
  input: SellerListingInput,
  photos: Buffer[],
): Promise<SellerListing> {
  return inQueue(async () => {
    const id = `s-${Date.now().toString(36)}${randomBytes(3).toString("hex")}`;
    const folder = path.join(UPLOADS, id);
    await mkdir(folder, { recursive: true });
    const names: string[] = [];
    for (const [index, photo] of photos.entries()) {
      const name = `${index + 1}.jpg`;
      await writeFile(path.join(folder, name), photo);
      names.push(name);
    }

    const listing: SellerListing = {
      ...input,
      id,
      sellerId,
      status: "moderation",
      photos: names,
      createdAt: new Date().toISOString(),
    };
    await save([...(await load()), listing]);
    return listing;
  });
}

// Все поданные объявления, свежие первыми (для админки)
export async function getAllSellerListings(): Promise<SellerListing[]> {
  return (await load()).sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

// Объявления, которые видны на сайте: одобренные и проданные
export async function getPublishedSellerListings(): Promise<SellerListing[]> {
  return (await load()).filter((listing) => listing.status === "active" || listing.status === "sold");
}

// Решение админа по объявлению. Возвращает, нашлось ли объявление.
export function setSellerListingStatus(
  id: string,
  status: SellerListingStatus,
  rejectReason?: string,
): Promise<boolean> {
  return inQueue(async () => {
    const listings = await load();
    const listing = listings.find((item) => item.id === id);
    if (!listing) return false;
    listing.status = status;
    listing.rejectReason = status === "rejected" ? rejectReason || undefined : undefined;
    // Дату публикации ставим один раз: при повторной публикации объявление не прыгает наверх ленты
    if (status === "active" && !listing.publishedAt) listing.publishedAt = new Date().toISOString();
    await save(listings);
    return true;
  });
}

// Удаляет объявление и его фото. Чужое объявление удалить нельзя. Возвращает, было ли что удалять.
export function deleteSellerListing(sellerId: string, id: string): Promise<boolean> {
  return inQueue(async () => {
    const listings = await load();
    const listing = listings.find((item) => item.id === id && item.sellerId === sellerId);
    if (!listing) return false;
    await save(listings.filter((item) => item !== listing));
    await rm(path.join(UPLOADS, listing.id), { recursive: true, force: true });
    return true;
  });
}

// Путь к файлу фото на диске. Принимаем только имена вида s-abc123 и 1.jpg,
// чтобы через адрес нельзя было прочитать другие файлы компьютера.
export function sellerPhotoFile(id: string, file: string): string | undefined {
  if (!/^s-[a-z0-9]{6,40}$/.test(id) || !/^\d{1,2}\.jpg$/.test(file)) return undefined;
  return path.join(UPLOADS, id, file);
}

// Адрес фото для страницы: /api/seller/photo/s-abc123/1.jpg
export function sellerPhotoUrl(id: string, file: string) {
  return `/api/seller/photo/${id}/${file}`;
}
