// Страница «Подать объявление». Адрес: /sell

import type { Metadata } from "next";
import { SellForm } from "./SellForm";

export const metadata: Metadata = { title: "Подать объявление" };

export default function SellPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="text-2xl font-bold">Подать объявление</h1>
      <p className="mt-1 mb-6 text-slate-500">Бесплатно. Заполнение займёт пару минут.</p>
      <SellForm />
    </div>
  );
}
