// Страница «Подать объявление». Адрес: /sell
// После отправки объявление сохраняется и появляется в кабинете продавца (/cabinet).

import type { Metadata } from "next";
import Link from "next/link";
import { getBrandModels } from "@/lib/listings";
import { MAX_PHOTOS } from "@/lib/seller-listings";
import { SellForm } from "./SellForm";

export const metadata: Metadata = { title: "Подать объявление" };

export default function SellPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="text-2xl font-bold">Подать объявление</h1>
      <p className="mt-1 mb-6 text-slate-500">
        Бесплатно. Заполнение займёт пару минут. Ваши объявления хранятся в{" "}
        <Link href="/cabinet" className="text-brand-700 hover:underline">
          кабинете продавца
        </Link>
        .
      </p>
      <SellForm brands={getBrandModels()} maxPhotos={MAX_PHOTOS} />
    </div>
  );
}
