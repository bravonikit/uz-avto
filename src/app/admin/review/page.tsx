// Админка, вкладка «Ручной разбор»: то, что парсер не решил сам. Адрес: /admin/review
//   ?tab=pairs   одна машина у двух продавцов или разные (по умолчанию)
//   ?tab=prices  странные цены, которые сейчас скрыты на сайте
// Решения читает парсер при следующем прогоне, подробнее в src/lib/review.ts.

import Link from "next/link";
import { Suspense } from "react";
import { isAdmin } from "@/lib/admin";
import { formatDate, formatMileage, formatPrice } from "@/lib/format";
import { getListing, listingTitle } from "@/lib/listings";
import { getPairQueue, getPriceQueue, type PairCandidate, type PriceSuspect } from "@/lib/review";
import { decidePairAction, decidePriceAction } from "../actions";

const SHOW = 10; // сколько карточек показываем за раз: после решения подтягиваются следующие

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export default function ReviewPage({ searchParams }: Props) {
  return (
    <Suspense fallback={<p className="text-slate-400">Загружаем очередь…</p>}>
      <Review searchParams={searchParams} />
    </Suspense>
  );
}

async function Review({ searchParams }: Props) {
  if (!(await isAdmin())) return null;
  const [params, pairs, prices] = await Promise.all([searchParams, getPairQueue(), getPriceQueue()]);
  const tab = params.tab === "prices" ? "prices" : "pairs";
  const tabClass = (active: boolean) =>
    `rounded-xl px-3 py-1.5 text-sm font-medium ${active ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100"}`;

  return (
    <>
      <div className="mb-2 flex flex-wrap gap-2">
        <Link href="/admin/review" className={tabClass(tab === "pairs")}>
          Одна машина? · {pairs.pairs.length}
        </Link>
        <Link href="/admin/review?tab=prices" className={tabClass(tab === "prices")}>
          Странные цены · {prices.suspects.length}
        </Link>
      </div>
      <p className="mb-5 text-xs text-slate-400">
        Решения сохраняются сразу, а на сайте учитываются после следующего прогона парсера.{" "}
        {tab === "pairs" ? `Уже решено пар: ${pairs.decided}.` : `Уже решено цен: ${prices.decided}.`}
      </p>

      {tab === "pairs" ? (
        pairs.pairs.length === 0 ? (
          <Empty text="Пар на проверку нет." />
        ) : (
          <ul className="max-w-3xl space-y-4">
            {pairs.pairs.slice(0, SHOW).map((pair) => (
              <Pair key={`${pair.first.id}|${pair.second.id}`} pair={pair} />
            ))}
          </ul>
        )
      ) : prices.suspects.length === 0 ? (
        <Empty text="Странных цен на проверку нет." />
      ) : (
        <ul className="max-w-3xl space-y-4">
          {prices.suspects.slice(0, SHOW).map((suspect) => (
            <Suspect key={suspect.id} suspect={suspect} />
          ))}
        </ul>
      )}
    </>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="rounded-2xl bg-white p-8 text-center text-slate-500 shadow-sm ring-1 ring-slate-200">{text}</p>;
}

const button = "rounded-xl px-4 py-2 text-sm font-semibold";
const light = `${button} text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50`;

// Маленькая карточка машины: фото, канал, что распознали, ссылки на пост и на нашу страницу
function Mini({ id, account, price, url }: { id: string; account: string; price: number | null; url: string }) {
  const listing = getListing(id);
  return (
    <div className="min-w-0">
      {listing?.image ? (
        // eslint-disable-next-line @next/next/no-img-element -- маленькое фото для сравнения
        <img src={listing.image} alt="" loading="lazy" className="aspect-[4/3] w-full rounded-xl bg-slate-100 object-cover" />
      ) : (
        <div className="flex aspect-[4/3] w-full items-center justify-center rounded-xl bg-slate-100 text-xs text-slate-400">
          нет фото
        </div>
      )}
      <p className="mt-2 truncate text-xs text-slate-500">@{account}</p>
      <p className="font-bold">{price ? formatPrice(price, "USD") : "без цены"}</p>
      {listing && (
        <p className="text-sm text-slate-600">
          {listingTitle(listing)}
          {listing.mileage !== undefined && ` · ${formatMileage(listing.mileage)}`}
          {` · ${formatDate(listing.createdAt)}`}
          {listing.isSold && " · продано"}
        </p>
      )}
      <p className="mt-1 flex flex-wrap gap-x-3 text-sm">
        <a href={url} target="_blank" rel="noopener noreferrer" className="text-brand-700 hover:underline">
          Пост ↗
        </a>
        {listing && (
          <Link href={`/cars/${id}`} target="_blank" className="text-brand-700 hover:underline">
            На сайте ↗
          </Link>
        )}
      </p>
    </div>
  );
}

function Pair({ pair }: { pair: PairCandidate }) {
  return (
    <li className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
      <h3 className="mb-3 font-bold">{pair.car}</h3>
      <div className="grid grid-cols-2 gap-4">
        <Mini {...pair.first} />
        <Mini {...pair.second} />
      </div>
      <form action={decidePairAction} className="mt-4 flex flex-wrap gap-2">
        <input type="hidden" name="first" value={pair.first.id} />
        <input type="hidden" name="second" value={pair.second.id} />
        <button type="submit" name="decision" value="same" className={`${button} bg-slate-900 text-white hover:bg-slate-700`}>
          Одна машина
        </button>
        <button type="submit" name="decision" value="different" className={light}>
          Разные машины
        </button>
      </form>
    </li>
  );
}

function Suspect({ suspect }: { suspect: PriceSuspect }) {
  const listing = getListing(suspect.id);
  return (
    <li className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
      <div className="grid gap-4 sm:grid-cols-[220px_1fr]">
        <Mini id={suspect.id} account={suspect.account} price={suspect.price} url={suspect.url} />
        <div className="min-w-0">
          <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
            Цена {suspect.price ? formatPrice(suspect.price, "USD") : "не указана"}: {suspect.reason}
          </p>
          {listing?.description && (
            <p className="mt-2 max-h-48 overflow-auto text-sm leading-relaxed whitespace-pre-line text-slate-700">
              {listing.description}
            </p>
          )}
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        {suspect.price !== null && (
          <form action={decidePriceAction}>
            <input type="hidden" name="id" value={suspect.id} />
            <input type="hidden" name="decision" value="keep" />
            <button type="submit" className={`${button} bg-slate-900 text-white hover:bg-slate-700`}>
              Цена верная
            </button>
          </form>
        )}
        <form action={decidePriceAction}>
          <input type="hidden" name="id" value={suspect.id} />
          <input type="hidden" name="decision" value="none" />
          <button type="submit" className={light}>
            В посте нет цены
          </button>
        </form>
        <form action={decidePriceAction} className="flex gap-2">
          <input type="hidden" name="id" value={suspect.id} />
          <input type="hidden" name="decision" value="fix" />
          <input
            name="price"
            inputMode="numeric"
            placeholder="Верная цена, $"
            className="w-36 rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500"
          />
          <button type="submit" className={light}>
            Исправить
          </button>
        </form>
      </div>
    </li>
  );
}
