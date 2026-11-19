// Страница одного объявления. Адрес: /cars/DfhLAoxR1JB
// Папка [id] в квадратных скобках = «любое значение» в этом месте адреса.

import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { notFound } from "next/navigation";
import { Freshness } from "@/components/Freshness";
import { Gallery } from "@/components/Gallery";
import { ListingCard } from "@/components/ListingCard";
import { ListingPhoto } from "@/components/ListingPhoto";
import { formatDate, formatMileage, formatPrice } from "@/lib/format";
import {
  countSellerListings,
  getAllListingIds,
  getSimilarListings,
  listingTitle,
  priceInSum,
  LIQUIDITY_LABELS,
  MARKET_COLORS,
  MARKET_LABELS,
  PHOTO_QUALITY_NOTES,
  PRICE_TYPE_LABELS,
  SOURCE_LABELS,
} from "@/lib/listings";
import { findListing } from "@/lib/published";

// Заранее (при сборке) создаём страницы для всех объявлений —
// так они открываются мгновенно.
export function generateStaticParams() {
  return getAllListingIds().map((id) => ({ id }));
}

export async function generateMetadata({ params }: PageProps<"/cars/[id]">): Promise<Metadata> {
  const listing = await findListing((await params).id);
  if (!listing) return { title: "Объявление не найдено" };
  return { title: `${listingTitle(listing)} — ${formatPrice(listing.price, listing.currency)}` };
}

// Номер объявления берётся из адреса, поэтому сама страница показывается «на лету»,
// а пока грузится, видна заглушка (так же устроен список /cars).
export default function ListingPage({ params }: PageProps<"/cars/[id]">) {
  return (
    <Suspense fallback={<ListingSkeleton />}>
      <ListingContent params={params} />
    </Suspense>
  );
}

function ListingSkeleton() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="h-8 w-2/3 animate-pulse rounded-lg bg-slate-200" />
      <div className="mt-5 grid gap-8 lg:grid-cols-[1fr_360px]">
        <div className="aspect-[4/3] animate-pulse rounded-2xl bg-slate-200" />
        <div className="h-64 animate-pulse rounded-2xl bg-slate-200" />
      </div>
    </div>
  );
}

async function ListingContent({ params }: Pick<PageProps<"/cars/[id]">, "params">) {
  // Объявление может быть собранным из Telegram или поданным продавцом через кабинет
  const listing = await findListing((await params).id);
  if (!listing) notFound();
  const similar = getSimilarListings(listing);

  // Показываем только характеристики, которые известны
  const specs = (
    [
      ["Год выпуска", listing.year],
      ["Пробег", listing.mileage !== undefined ? formatMileage(listing.mileage) : undefined],
      ["Кузов", listing.bodyType],
      ["Цвет", listing.color?.name],
      ["Салон", listing.interiorColor],
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
        {/* Марку и модель показываем, только если их удалось определить */}
        {listing.brand && (
          <>
            {" / "}
            <Link
              href={`/cars?brand=${encodeURIComponent(listing.brand)}`}
              className="hover:text-slate-900"
            >
              {listing.brand}
            </Link>
          </>
        )}
        {listing.model && (
          <>
            {" / "}
            <span className="text-slate-700">{listing.model}</span>
          </>
        )}
      </nav>

      <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold sm:text-3xl">{listingTitle(listing)}</h1>
          <p className="mt-1 text-sm text-slate-500">
            Размещено {formatDate(listing.createdAt)} (<Freshness date={listing.createdAt} />) · №{" "}
            {listing.id}
          </p>
          {listing.isSold && (
            <p className="mt-3 rounded-xl bg-slate-100 px-4 py-3 text-sm font-medium text-slate-700">
              Продавец отметил, что машина продана. Объявление оставлено для истории цен.
            </p>
          )}

          {listing.photoQuality !== "good" && (
            <p className="mt-3 rounded-xl bg-amber-50 px-4 py-2 text-sm text-amber-800">
              {PHOTO_QUALITY_NOTES[listing.photoQuality]}
            </p>
          )}

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

          {listing.photos && listing.photos.length > 1 && (
            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
              {listing.photos.slice(1).map((photo) => (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  key={photo}
                  src={photo}
                  alt={listingTitle(listing)}
                  loading="lazy"
                  className="aspect-[4/3] w-full rounded-xl object-cover ring-1 ring-slate-200"
                />
              ))}
            </div>
          )}
          {listing.preview && (
            <p className="mt-3 text-sm text-slate-500">
              {listing.preview.kind === "generated" && "Фото сделаны ИИ по видео продавца, настоящие кадры смотрите в его посте. "}
              {listing.preview.kind === "outpaint" && "Края обложки дорисованы ИИ, сама машина с фото продавца. "}
              {listing.preview.priceSource === "voice" &&
                `Цена взята из видео со слов продавца${listing.preview.priceApprox ? ", приблизительно" : ""}. `}
              {listing.preview.priceSource === "overlay" && "Цена взята из надписи на видео. "}
            </p>
          )}

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

          {(listing.summary || listing.speech) && (
            <>
              <h2 className="mt-8 mb-3 text-xl font-bold">Коротко о машине</h2>
              {listing.summary && <p className="leading-relaxed text-slate-700">{listing.summary}</p>}
              {listing.speech && (
                <p className="mt-2 leading-relaxed text-slate-700">
                  <span className="font-medium">Из видео продавца:</span> {listing.speech}
                </p>
              )}
              {listing.transcript && (
                <details className="mt-2 text-slate-700">
                  <summary className="cursor-pointer text-sm font-medium text-slate-500 hover:text-slate-700">
                    Что говорит продавец в видео, дословно
                  </summary>
                  <p className="mt-2 whitespace-pre-line text-sm leading-relaxed">{listing.transcript}</p>
                  <p className="mt-1 text-xs text-slate-400">Расшифровка сделана автоматически, возможны ошибки в словах.</p>
                </details>
              )}
              <p className="mt-2 text-xs text-slate-400">
                Пересказ составлен автоматически по тексту{listing.speech ? " и ролику" : ""} продавца. Точные слова продавца ниже.
              </p>
            </>
          )}

          <h2 className="mt-8 mb-3 text-xl font-bold">
            {listing.source ? `Описание из ${SOURCE_LABELS[listing.source.platform]}` : "Комментарий продавца"}
          </h2>
          {/* whitespace-pre-line сохраняет переносы строк, как в посте */}
          <p className="leading-relaxed whitespace-pre-line text-slate-700">{listing.description}</p>
        </div>

        <aside className="lg:sticky lg:top-20 lg:self-start">
          <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
            <p className={`text-3xl font-extrabold ${listing.isSold ? "text-slate-400 line-through" : ""}`}>
              {formatPrice(listing.price, listing.currency)}
            </p>
            {listing.price !== undefined && listing.currency === "USD" && (
              <p className="mt-1 text-sm text-slate-500">
                ≈ {formatPrice(priceInSum(listing))} по тестовому курсу
              </p>
            )}
            {listing.priceType && (
              <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
                {PRICE_TYPE_LABELS[listing.priceType]}: это цена не за машину в наличии, уточняйте у продавца
                срок и полную стоимость.
              </p>
            )}
            {listing.market && (
              <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <p className={`font-medium ${MARKET_COLORS[listing.market.label]}`}>
                  {MARKET_LABELS[listing.market.label]}
                </p>
                <p className="text-slate-600">
                  Похожие машины: около {formatPrice(listing.market.price, "USD")}, обычно от{" "}
                  {formatPrice(listing.market.low, "USD")} до {formatPrice(listing.market.high, "USD")}. Сравнили с{" "}
                  {listing.market.count} объявлениями той же модели и близкого года.
                </p>
              </div>
            )}
            {listing.liquidity && (
              <p className="mt-2 text-sm text-slate-600">{LIQUIDITY_LABELS[listing.liquidity]} (по отметкам «продано»)</p>
            )}
            {listing.alsoAt && listing.alsoAt.length > 0 && (
              <div className="mt-2 text-sm text-slate-600">
                Эта же машина в других каналах:
                <ul className="mt-1 space-y-0.5">
                  {listing.alsoAt.map((place) => (
                    <li key={place.url}>
                      <a href={place.url} target="_blank" rel="noopener noreferrer" className="text-brand-700 hover:underline">
                        {place.account}
                      </a>
                      {place.price !== undefined && `: ${formatPrice(place.price, "USD")}`}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {listing.price === undefined && (
              <p className="mt-1 text-sm text-slate-500">Продавец не указал цену в посте, уточняйте у него.</p>
            )}
            {listing.downPayment !== undefined && (
              <p className="mt-2 text-sm font-medium text-slate-800">
                В рассрочку, первый взнос от {formatPrice(listing.downPayment, "USD")}
              </p>
            )}

            {listing.seller && (
              <>
                <div className="mt-5 flex items-center gap-3">
                  <div className="flex size-11 items-center justify-center rounded-full bg-slate-100 text-lg font-bold text-slate-800">
                    {listing.seller.name[0]}
                  </div>
                  <div>
                    <p className="font-semibold">{listing.seller.name}</p>
                    <p className="text-sm text-slate-500">{listing.seller.type}</p>
                  </div>
                </div>
                <a
                  href={`tel:${listing.seller.phone.replace(/[^\d+]/g, "")}`}
                  className="mt-5 block rounded-xl bg-brand-600 px-4 py-3 text-center font-semibold text-white hover:bg-brand-700"
                >
                  {listing.seller.phone}
                </a>
              </>
            )}

            {listing.source && (
              <>
                <p className="mt-5 text-sm text-slate-500">
                  Объявление из {SOURCE_LABELS[listing.source.platform]}{" "}
                  <span className="font-medium text-slate-700">@{listing.source.account}</span>.
                  Контакты продавца — в описании.
                </p>
                <a
                  href={listing.source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-4 block rounded-xl bg-brand-600 px-4 py-3 text-center font-semibold text-white hover:bg-brand-700"
                >
                  Открыть в {SOURCE_LABELS[listing.source.platform]} ↗
                </a>
                <Link
                  href={`/cars?seller=${encodeURIComponent(listing.source.account)}`}
                  className="mt-2 block rounded-xl px-4 py-3 text-center text-sm font-semibold text-slate-900 ring-1 ring-slate-300 hover:bg-slate-50"
                >
                  Все объявления продавца ({countSellerListings(listing.source.account)})
                </Link>
              </>
            )}

            <p className="mt-3 text-xs text-slate-400">
              Не переводите предоплату, пока не увидели машину и документы.
            </p>
          </div>
        </aside>
      </div>

      {similar.length > 0 && (
        <section className="mt-10">
          <div className="flex items-baseline justify-between gap-4">
            <h2 className="text-xl font-bold">Похожие объявления</h2>
            <Link
              href={`/cars?brand=${encodeURIComponent(listing.brand)}&model=${encodeURIComponent(listing.model)}`}
              className="text-sm font-medium text-brand-700 hover:underline"
            >
              Все {listing.brand} {listing.model}
            </Link>
          </div>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {similar.map((car) => (
              <ListingCard key={car.id} listing={car} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
