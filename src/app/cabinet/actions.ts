"use server";
// Действия в кабинете продавца. Выполняются только на сервере.

import { refresh } from "next/cache";
import { deleteSellerListing } from "@/lib/seller-listings";
import { getSellerId } from "@/lib/seller-session";

// Удаляет объявление продавца вместе с фото. Чужое объявление удалить нельзя.
export async function deleteListing(formData: FormData) {
  const id = formData.get("id");
  const sellerId = await getSellerId();
  if (typeof id !== "string" || !sellerId) return;
  await deleteSellerListing(sellerId, id);
  refresh(); // перерисовать список в кабинете
}
