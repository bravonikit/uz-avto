// Общий каркас для всех страниц: шрифт, шапка, подвал.

import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Suspense } from "react";
import { Header } from "@/components/Header";
import { ViewTracker } from "@/components/ViewTracker";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin", "cyrillic"],
});

export const metadata: Metadata = {
  title: {
    default: "Mashina Bashina — купить и продать авто в Узбекистане",
    template: "%s — Mashina Bashina",
  },
  description: "Объявления о продаже автомобилей в Ташкенте и по всему Узбекистану. Цены в сумах.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ru" className={`${inter.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col bg-slate-50 text-slate-900">
        <Header />
        {/* Счётчик просмотров: ничего не рисует, только считает открытия страниц */}
        <Suspense fallback={null}>
          <ViewTracker />
        </Suspense>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-slate-200 bg-white py-6 text-center text-sm text-slate-400">
          Mashina Bashina · тестовая версия, объявления взяты из Instagram и Telegram
        </footer>
      </body>
    </html>
  );
}
