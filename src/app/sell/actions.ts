"use server";
// "use server" значит: эти функции выполняются только на сервере.
// Браузер присылает сюда данные формы и фото, мы их проверяем и сохраняем.

import { redirect } from "next/navigation";
import {
  BODY_TYPES,
  CITIES,
  DRIVES,
  FUEL_TYPES,
  NEWEST_YEAR,
  OLDEST_YEAR,
  TRANSMISSIONS,
} from "@/lib/catalog";
import { parseNumber } from "@/lib/format";
import { addSellerListing, MAX_PHOTO_BYTES, MAX_PHOTOS } from "@/lib/seller-listings";
import { ensureSellerId } from "@/lib/seller-session";

export type SellFormState = {
  status: "idle" | "error";
  errors?: Partial<Record<string, string>>;
};

// Значение из списка вариантов или ничего, если прислали что-то другое
function oneOf(items: readonly string[], value: string) {
  return items.includes(value) ? value : undefined;
}

// Настоящий JPEG начинается с байтов FF D8 FF
function isJpeg(bytes: Buffer) {
  return bytes.length > 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
}

export async function submitListing(
  _prevState: SellFormState,
  formData: FormData,
): Promise<SellFormState> {
  const text = (name: string) => {
    const value = formData.get(name);
    return typeof value === "string" ? value.trim() : "";
  };

  const errors: Record<string, string> = {};

  const brand = text("brand");
  const model = text("model");
  const year = parseNumber(text("year"));
  const mileage = parseNumber(text("mileage"));
  const price = parseNumber(text("price"));
  const currency = text("currency") === "UZS" ? "UZS" : "USD";
  const city = text("city");
  const color = text("color");
  const description = text("description");
  const name = text("name");
  const phone = text("phone").replace(/\D/g, "");
  const telegram = text("telegram").replace(/^@/, "");

  if (!brand || brand.length > 40) errors.brand = "Укажите марку";
  if (!model || model.length > 40) errors.model = "Укажите модель";
  if (!year || year < OLDEST_YEAR || year > NEWEST_YEAR) errors.year = "Укажите год";
  if (mileage === undefined || mileage > 2_000_000) errors.mileage = "Укажите пробег (0, если машина новая)";
  if (!price || price < (currency === "USD" ? 500 : 1_000_000) || price > 100_000_000_000) {
    errors.price = currency === "USD" ? "Укажите цену в долларах (от 500)" : "Укажите цену в сумах (от 1 000 000)";
  }
  if (!CITIES.includes(city)) errors.city = "Выберите город";
  if (color.length > 30) errors.color = "Слишком длинное название цвета";
  if (description.length > 3000) errors.description = "Слишком длинное описание (до 3000 знаков)";
  if (!name || name.length > 60) errors.name = "Как к вам обращаться?";
  // Узбекский номер: 998 + 9 цифр
  if (!/^998\d{9}$/.test(phone)) errors.phone = "Формат: +998 90 123 45 67";
  if (telegram && !/^[a-zA-Z0-9_]{4,32}$/.test(telegram)) errors.telegram = "Ник в Telegram, например @aziz_auto";

  // Фото: браузер уже уменьшил их и перевёл в JPEG (см. SellForm.tsx)
  const files = formData.getAll("photos").filter((item): item is File => item instanceof File && item.size > 0);
  const photos: Buffer[] = [];
  if (files.length === 0) errors.photos = "Добавьте хотя бы одно фото";
  else if (files.length > MAX_PHOTOS) errors.photos = `Не больше ${MAX_PHOTOS} фото`;
  else {
    for (const file of files) {
      const bytes = file.size <= MAX_PHOTO_BYTES ? Buffer.from(await file.arrayBuffer()) : undefined;
      if (!bytes || !isJpeg(bytes)) {
        errors.photos = "Одно из фото не подошло. Удалите его и добавьте заново.";
        break;
      }
      photos.push(bytes);
    }
  }

  if (Object.keys(errors).length > 0) return { status: "error", errors };

  const sellerId = await ensureSellerId();
  const listing = await addSellerListing(
    sellerId,
    {
      brand,
      model,
      year: year!,
      mileage: mileage!,
      price: price!,
      currency,
      city,
      bodyType: oneOf(BODY_TYPES, text("bodyType")),
      fuel: oneOf(FUEL_TYPES, text("fuel")),
      transmission: oneOf(TRANSMISSIONS, text("transmission")),
      drive: oneOf(DRIVES, text("drive")),
      color: color || undefined,
      description,
      name,
      phone,
      telegram: telegram || undefined,
    },
    photos,
  );

  // Сразу показываем продавцу его кабинет с новым объявлением
  redirect(`/cabinet?new=${listing.id}`);
}
