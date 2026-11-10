// Страница одного объявления. Адрес: /cars/DfhLAoxR1JB
// Папка [id] в квадратных скобках = «любое значение» в этом месте адреса.

import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Gallery } from "@/components/Gallery";
import { ListingPhoto } from "@/components/ListingPhoto";
import { formatDate, formatMileage, formatPrice } from "@/lib/format";
import { getAllListingIds, getListing, listingTitle, priceInSum } from "@/lib/listings";

// Заранее (при сборке) создаём страницы для всех объявлений —
// так они открываются мгновенно.
export function generateStaticParams() {
  return getAllListingIds().map((id) => ({ id }));
}

export async function generateMetadata({ params }: PageProps<"/cars/[id]">): Promise<Metadata> {
  const listing = getListing((await params).id);
  if (!listing) return { title: "Объявление не найдено" };
  return { title: `${listingTitle(listing)} — ${formatPrice(listing.price, listing.currency)}` };
}

export default async function ListingPage({ params }: PageProps<"/cars/[id]">) {
  const listing = getListing((await params).id);
  if (!listing) notFound();

  // Показываем только характеристики, которые известны
  const specs = (
    [
      ["Год выпуска", listing.year],
      ["Пробег", listing.mileage !== undefined ? formatMileage(listing.mileage) : undefined],
      ["Кузов", listing.bodyType],
      ["Цвет", listing.color?.name],
      ["Двигатель", listing.engine],
      ["Топливо", listing.fuel],
      ["Коробка", listing.transmission],
      ["Привод", listing.drive],
      ["Город", listing.city],
    ] as const
  ).filter(([, value]) => value !== undefined);

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
          <h1 className="text-2xl font-bold sm:text-3xl">{listingTitle(listing)}</h1>
          <p className="mt-1 text-sm text-slate-500">
            Размещено {formatDate(listing.createdAt)} · № {listing.id}
          </p>

          <div className="mt-5">
            {listing.image ? (
              <ListingPhoto
                listing={listing}
                sizes="(min-width: 1024px) 760px, 100vw"
                priority
                className="overflow-hidden rounded-2xl ring-1 ring-slate-200"
              />
            ) : (
              <Gallery listing={listing} />
            )}
          </div>

          <h2 className="mt-8 mb-3 text-xl font-bold">Характеристики</h2>
          {specs.length > 0 ? (
            <dl className="grid gap-x-8 sm:grid-cols-2">
              {specs.map(([label, value]) => (
                <div key={label} className="flex justify-between gap-4 border-b border-slate-200 py-2.5">
                  <dt className="text-slate-500">{label}</dt>
                  <dd className="text-right font-medium">{value}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-slate-500">Не указаны — смотрите описание.</p>
          )}

          <h2 className="mt-8 mb-3 text-xl font-bold">
            {listing.source ? "Описание из Instagram" : "Комментарий продавца"}
          </h2>
          {/* whitespace-pre-line сохраняет переносы строк, как в посте */}
          <p className="leading-relaxed whitespace-pre-line text-slate-700">{listing.description}</p>
        </div>

        <aside className="lg:sticky lg:top-20 lg:self-start">
          <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
            <p className="text-3xl font-extrabold">{formatPrice(listing.price, listing.currency)}</p>
            {listing.currency === "USD" && (
              <p className="mt-1 text-sm text-slate-500">
                ≈ {formatPrice(priceInSum(listing))} по тестовому курсу
              </p>
            )}

            {listing.seller && (
              <>
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
              </>
            )}

            {listing.source && (
              <>
                <p className="mt-5 text-sm text-slate-500">
                  Объявление из Instagram{" "}
                  <span className="font-medium text-slate-700">@{listing.source.account}</span>.
                  Контакты продавца — в описании.
                </p>
                <a
                  href={listing.source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-4 block rounded-xl bg-gradient-to-r from-fuchsia-600 to-orange-500 px-4 py-3 text-center font-semibold text-white hover:opacity-90"
                >
                  Открыть в Instagram ↗
                </a>
              </>
            )}

            <p className="mt-3 text-xs text-slate-400">
              Не переводите предоплату, пока не увидели машину и документы.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
