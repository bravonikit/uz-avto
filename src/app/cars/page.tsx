// Лента объявлений с фильтрами. Адрес: /cars?brand=Kia&city=Ташкент

import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { ListingCard } from "@/components/ListingCard";
import { SearchForm } from "@/components/SearchForm";
import { filtersFromSearchParams, getBrandModels, searchListings } from "@/lib/listings";

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
  const filters = filtersFromSearchParams(await searchParams);
  const listings = searchListings(filters);

  return (
    <>
      <div className="mb-6 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
        {/* key заставляет форму обновиться, если фильтры в адресе поменялись */}
        <SearchForm key={JSON.stringify(filters)} brands={getBrandModels()} initial={filters} />
      </div>
      <p className="mb-4 text-sm text-slate-500">Найдено объявлений: {listings.length}</p>
      {listings.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {listings.map((listing) => (
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
    </>
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
