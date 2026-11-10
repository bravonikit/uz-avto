// Страница одного объявления. Адрес: /cars/1001
// Папка [id] в квадратных скобках = «любое значение» в этом месте адреса.

import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Gallery } from "@/components/Gallery";
import { formatDate, formatMileage, formatPrice } from "@/lib/format";
import { getAllListingIds, getListing } from "@/lib/listings";

// Заранее (при сборке) создаём страницы для всех тестовых объявлений —
// так они открываются мгновенно.
export function generateStaticParams() {
  return getAllListingIds().map((id) => ({ id }));
}

export async function generateMetadata({ params }: PageProps<"/cars/[id]">): Promise<Metadata> {
  const listing = getListing((await params).id);
  if (!listing) return { title: "Объявление не найдено" };
  return {
    title: `${listing.brand} ${listing.model} ${listing.year} — ${formatPrice(listing.price)}`,
  };
}

export default async function ListingPage({ params }: PageProps<"/cars/[id]">) {
  const listing = getListing((await params).id);
  if (!listing) notFound();

  const specs: [string, string | number][] = [
    ["Год выпуска", listing.year],
    ["Пробег", formatMileage(listing.mileage)],
    ["Кузов", listing.bodyType],
    ["Цвет", listing.color.name],
    ["Двигатель", listing.engine],
    ["Топливо", listing.fuel],
    ["Коробка", listing.transmission],
    ["Привод", listing.drive],
    ["Город", listing.city],
  ];

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <nav className="mb-4 text-sm text-slate-500">
        <Link href="/cars" className="hover:text-slate-900">
          Объявления
        </Link>
        {" / "}
        <Link
          href={`/cars?brand=${encodeURIComponent(listing.brand)}`}
          className="hover:text-slate-900"
        >
          {listing.brand}
        </Link>
        {" / "}
        <span className="text-slate-700">{listing.model}</span>
      </nav>

      <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold sm:text-3xl">
            {listing.brand} {listing.model}, {listing.year}
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Размещено {formatDate(listing.createdAt)} · № {listing.id}
          </p>

          <div className="mt-5">
            <Gallery listing={listing} />
          </div>

          <h2 className="mt-8 mb-3 text-xl font-bold">Характеристики</h2>
          <dl className="grid gap-x-8 sm:grid-cols-2">
            {specs.map(([label, value]) => (
              <div key={label} className="flex justify-between gap-4 border-b border-slate-200 py-2.5">
                <dt className="text-slate-500">{label}</dt>
                <dd className="text-right font-medium">{value}</dd>
              </div>
            ))}
          </dl>

          <h2 className="mt-8 mb-3 text-xl font-bold">Комментарий продавца</h2>
          <p className="leading-relaxed text-slate-700">{listing.description}</p>
        </div>

        <aside className="lg:sticky lg:top-20 lg:self-start">
          <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
            <p className="text-3xl font-extrabold">{formatPrice(listing.price)}</p>
            <div className="mt-5 flex items-center gap-3">
              <div className="flex size-11 items-center justify-center rounded-full bg-emerald-100 text-lg font-bold text-emerald-700">
                {listing.seller.name[0]}
              </div>
              <div>
                <p className="font-semibold">{listing.seller.name}</p>
                <p className="text-sm text-slate-500">{listing.seller.type}</p>
              </div>
            </div>
            <a
              href={`tel:${listing.seller.phone.replace(/[^\d+]/g, "")}`}
              className="mt-5 block rounded-xl bg-emerald-600 px-4 py-3 text-center font-semibold text-white hover:bg-emerald-700"
            >
              {listing.seller.phone}
            </a>
            <p className="mt-3 text-xs text-slate-400">
              Не переводите предоплату, пока не увидели машину и документы.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
