// Главная страница: поиск + свежие объявления.

import Link from "next/link";
import { ListingCard } from "@/components/ListingCard";
import { SearchForm } from "@/components/SearchForm";
import { SiteStats } from "@/components/SiteStats";
import { countActiveListings, getBrandModels, getPopularBrands, searchListings } from "@/lib/listings";

export default function HomePage() {
  const latest = searchListings({ sort: "new" }).slice(0, 8);
  const brands = getBrandModels();
  const popularBrands = getPopularBrands();

  return (
    <>
      {/* Шапка: зелёный сверху плавно переходит в фон страницы (у body он bg-slate-50) */}
      <section className="bg-gradient-to-b from-emerald-700 via-emerald-500 via-45% to-slate-50 px-4 pt-12 pb-8 sm:pt-16">
        <div className="mx-auto max-w-6xl">
          <h1 className="text-3xl font-extrabold text-white sm:text-4xl">
            Купить авто в Узбекистане
          </h1>
          <p className="mt-2 text-emerald-50">
            Тысячи машин от владельцев и автосалонов — от Ташкента до Нукуса
          </p>
          <div className="mt-6 rounded-2xl bg-white p-4 shadow-xl sm:p-5">
            <SearchForm brands={brands} />
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            {popularBrands.map((brand) => (
              <Link
                key={brand}
                href={`/cars?brand=${encodeURIComponent(brand)}`}
                className="rounded-full bg-white/80 px-3 py-1 text-sm text-emerald-900 ring-1 ring-emerald-200 hover:bg-white"
              >
                {brand}
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-10">
        <div className="mb-5 flex items-baseline justify-between gap-4">
          <h2 className="text-2xl font-bold">Свежие объявления</h2>
          <Link href="/cars" className="text-sm font-medium text-emerald-700 hover:underline">
            Смотреть все →
          </Link>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {latest.map((listing) => (
            <ListingCard key={listing.id} listing={listing} />
          ))}
        </div>
        <SiteStats listings={countActiveListings()} />
      </section>
    </>
  );
}
