// Лента объявлений с фильтрами. Адрес: /cars?brand=Kia&city=Ташкент

import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { ListingCard } from "@/components/ListingCard";
import { SearchForm } from "@/components/SearchForm";
import { filtersFromSearchParams, getBrandModels, PAGE_SIZE, searchListings } from "@/lib/listings";
import { parseNumber } from "@/lib/format";

export const metadata: Metadata = { title: "Объявления о продаже авто" };

export default function CarsPage({ searchParams }: PageProps<"/cars">) {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="mb-5 text-2xl font-bold">Объявления о продаже авто</h1>
      {/* Фильтры берутся из адреса страницы, поэтому эта часть
          показывается «на лету», а пока грузится — заглушка */}
      <Suspense fallback={<ResultsSkeleton />}>
        <Results searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function Results({ searchParams }: Pick<PageProps<"/cars">, "searchParams">) {
  const params = await searchParams;
  const filters = filtersFromSearchParams(params);
  const listings = searchListings(filters);

  // Страницы: /cars?page=2. Показываем по PAGE_SIZE карточек, а не всё сразу
  const pageCount = Math.max(1, Math.ceil(listings.length / PAGE_SIZE));
  const page = Math.min(Math.max(1, Math.floor(parseNumber(params.page) ?? 1)), pageCount);
  const pageListings = listings.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  // Ссылка на другую страницу с теми же фильтрами
  const pageHref = (target: number) => {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (typeof value === "string" && value && key !== "page") query.set(key, value);
    }
    if (target > 1) query.set("page", String(target));
    const text = query.toString();
    return text ? `/cars?${text}` : "/cars";
  };

  return (
    <>
      <div className="mb-6 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
        {/* key заставляет форму обновиться, если фильтры в адресе поменялись */}
        <SearchForm key={JSON.stringify(filters)} brands={getBrandModels()} initial={filters} />
      </div>
      {filters.seller && (
        <p className="mb-3 text-sm">
          <span className="rounded-full bg-fuchsia-50 px-3 py-1 font-medium text-fuchsia-700 ring-1 ring-fuchsia-200">
            Продавец @{filters.seller}
          </span>
          <Link href="/cars" className="ml-2 text-emerald-700 hover:underline">
            показать всех
          </Link>
        </p>
      )}
      <p className="mb-4 text-sm text-slate-500">
        Найдено объявлений: {listings.length}
        {pageCount > 1 && ` · страница ${page} из ${pageCount}`}
      </p>
      {listings.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {pageListings.map((listing) => (
            <ListingCard key={listing.id} listing={listing} />
          ))}
        </div>
      ) : (
        <div className="rounded-2xl bg-white p-10 text-center ring-1 ring-slate-200">
          <p className="font-medium">По вашему запросу ничего не нашлось</p>
          <Link href="/cars" className="mt-2 inline-block text-sm text-emerald-700 hover:underline">
            Сбросить фильтры
          </Link>
        </div>
      )}
      {pageCount > 1 && <Pagination page={page} pageCount={pageCount} pageHref={pageHref} />}
    </>
  );
}

// Кнопки «Назад», номера страниц и «Вперёд» под лентой
function Pagination({
  page,
  pageCount,
  pageHref,
}: {
  page: number;
  pageCount: number;
  pageHref: (target: number) => string;
}) {
  // Показываем первую, последнюю и по две соседние с текущей: 1 … 4 5 [6] 7 8 … 159
  const numbers = Array.from({ length: pageCount }, (_, i) => i + 1).filter(
    (n) => n === 1 || n === pageCount || Math.abs(n - page) <= 2,
  );
  const button = "rounded-xl px-3 py-2 text-sm font-medium ring-1 ring-slate-200";
  return (
    <nav className="mt-8 flex flex-wrap items-center justify-center gap-2" aria-label="Страницы">
      {page > 1 && (
        <Link href={pageHref(page - 1)} className={`${button} bg-white text-slate-700 hover:bg-slate-50`}>
          ← Назад
        </Link>
      )}
      {numbers.map((n, i) => (
        <span key={n} className="flex items-center gap-2">
          {i > 0 && n - numbers[i - 1] > 1 && <span className="text-slate-400">…</span>}
          {n === page ? (
            <span className={`${button} bg-emerald-600 text-white ring-emerald-600`} aria-current="page">
              {n}
            </span>
          ) : (
            <Link href={pageHref(n)} className={`${button} bg-white text-slate-700 hover:bg-slate-50`}>
              {n}
            </Link>
          )}
        </span>
      ))}
      {page < pageCount && (
        <Link href={pageHref(page + 1)} className={`${button} bg-white text-slate-700 hover:bg-slate-50`}>
          Вперёд →
        </Link>
      )}
    </nav>
  );
}

function ResultsSkeleton() {
  return (
    <div className="grid animate-pulse gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} className="h-72 rounded-2xl bg-slate-200" />
      ))}
    </div>
  );
}
