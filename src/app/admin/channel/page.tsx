// Админка, вкладка «Канал»: как посты канала выглядят в Telegram и что из них получилось на сайте.
// При заходе берётся случайный канал и три его последних объявления. Адрес: /admin/channel
// Конкретный канал: /admin/channel?c=carsaleuzb

import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";
import { ListingCard } from "@/components/ListingCard";
import { isAdmin } from "@/lib/admin";
import { formatMileage, formatPrice } from "@/lib/format";
import {
  getChannelLatest,
  getTelegramChannels,
  MARKET_LABELS,
  PRICE_TYPE_LABELS,
  type Listing,
  type PhotoQuality,
} from "@/lib/listings";
import { TelegramPost } from "./TelegramPost";

const QUALITY_LABELS: Record<PhotoQuality, string> = {
  good: "хорошие фото",
  video: "только видео",
  bad: "плохие фото",
  mixed: "фото разного качества",
  unknown: "фото не проверены",
};

// Случайный элемент списка
function pickRandom<T>(list: T[]): T | undefined {
  return list[Math.floor(Math.random() * list.length)];
}

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export default function ChannelPage({ searchParams }: Props) {
  return (
    <Suspense fallback={<p className="text-slate-400">Выбираем канал…</p>}>
      <Channel searchParams={searchParams} />
    </Suspense>
  );
}

async function Channel({ searchParams }: Props) {
  if (!(await isAdmin())) return null;
  const params = await searchParams;
  await connection(); // случайный канал выбирается при каждом открытии, а не один раз при сборке

  const channels = getTelegramChannels();
  if (channels.length === 0) return <p className="text-slate-500">Объявлений из Telegram пока нет.</p>;
  const current = channels.find((channel) => channel.account === params.c) ?? pickRandom(channels)!;
  const next = pickRandom(channels.filter((channel) => channel !== current)) ?? current;
  const listings = getChannelLatest(current.account, 3);

  return (
    <>
      <div className="mb-6 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h2 className="text-xl font-bold">@{current.account}</h2>
          <span className="text-sm text-slate-500">
            {current.count} объявлений на сайте · {QUALITY_LABELS[listings[0]?.photoQuality ?? "unknown"]}
          </span>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
          <Link href={`/admin/channel?c=${next.account}`} className="rounded-xl bg-slate-900 px-4 py-2 font-semibold text-white hover:bg-slate-700">
            Другой случайный канал
          </Link>
          <a href={`https://t.me/${current.account}`} target="_blank" rel="noopener noreferrer" className="text-brand-700 hover:underline">
            Канал в Telegram ↗
          </a>
          <Link href={`/cars?seller=${encodeURIComponent(current.account)}`} className="text-brand-700 hover:underline">
            Все его объявления на сайте
          </Link>
          <form action="/admin/channel" className="flex gap-2">
            <select name="c" defaultValue={current.account} aria-label="Канал" className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm">
              {channels.map((channel) => (
                <option key={channel.account} value={channel.account}>
                  {channel.account} ({channel.count})
                </option>
              ))}
            </select>
            <button type="submit" className="rounded-xl px-3 py-2 font-medium text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50">
              Показать
            </button>
          </form>
        </div>
      </div>

      <div className="space-y-8">
        {listings.map((listing, index) => (
          <Comparison key={listing.id} listing={listing} number={index + 1} />
        ))}
      </div>
    </>
  );
}

// "https://t.me/carsaleuzb/83960" → "carsaleuzb/83960"
function telegramPost(url: string) {
  const match = /^https:\/\/t\.me\/([A-Za-z0-9_]+\/\d+)$/.exec(url);
  return match?.[1];
}

function Comparison({ listing, number }: { listing: Listing; number: number }) {
  const post = listing.source && telegramPost(listing.source.url);
  // Что удалось достать из поста. Пустое значение сразу видно: это то, что парсер не распознал.
  const parsed: [string, string | undefined][] = [
    ["Марка", listing.brand || undefined],
    ["Модель", listing.model || undefined],
    ["Год", listing.year?.toString()],
    ["Пробег", listing.mileage !== undefined ? formatMileage(listing.mileage) : undefined],
    ["Цена", listing.price !== undefined ? formatPrice(listing.price, listing.currency) : undefined],
    ["Топливо", listing.fuel],
    ["Цвет", listing.color?.name],
    ["Город", listing.city],
  ];
  // Оценку рынка считаем сами по похожим машинам, из поста её не достать
  const market = listing.market
    ? `${MARKET_LABELS[listing.market.label]}, похожие около ${formatPrice(listing.market.price, "USD")}`
    : "нет, мало похожих машин или не хватает данных";
  const notes = [
    listing.isSold && "продано",
    listing.priceType && PRICE_TYPE_LABELS[listing.priceType],
    listing.alsoAt && listing.alsoAt.length > 0 && `эта же машина ещё в ${listing.alsoAt.length} каналах`,
  ].filter(Boolean);

  return (
    <section>
      <h3 className="mb-3 text-sm font-semibold text-slate-500">Объявление {number} из последних</h3>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="min-w-0">
          <p className="mb-2 text-xs font-semibold tracking-wide text-slate-400 uppercase">В Telegram</p>
          {post ? <TelegramPost post={post} /> : <p className="text-sm text-slate-500">Пост не из Telegram.</p>}
          {listing.source && (
            <a href={listing.source.url} target="_blank" rel="noopener noreferrer" className="mt-2 inline-block text-sm text-brand-700 hover:underline">
              Открыть пост в Telegram ↗
            </a>
          )}
        </div>
        <div className="min-w-0">
          <p className="mb-2 text-xs font-semibold tracking-wide text-slate-400 uppercase">У нас на сайте</p>
          <div className="max-w-sm">
            <ListingCard listing={listing} />
          </div>
          <dl className="mt-4 max-w-sm text-sm">
            {parsed.map(([label, value]) => (
              <div key={label} className="flex justify-between gap-4 border-b border-slate-100 py-1.5">
                <dt className="text-slate-500">{label}</dt>
                <dd className={value ? "text-right font-medium" : "text-right text-red-600"}>{value ?? "не распознано"}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-2 max-w-sm text-sm text-slate-600">Оценка рынка: {market}.</p>
          {notes.length > 0 && <p className="mt-2 text-sm text-slate-600">Пометки: {notes.join(", ")}.</p>}
        </div>
      </div>
    </section>
  );
}
