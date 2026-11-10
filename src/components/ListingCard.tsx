// Карточка объявления в ленте: фото, цена, название, пробег, город.

import Link from "next/link";
import { ListingPhoto } from "./ListingPhoto";
import { formatDate, formatMileage, formatPrice } from "@/lib/format";
import { listingTitle, priceInSum, type Listing } from "@/lib/listings";

export function ListingCard({ listing }: { listing: Listing }) {
  // Показываем только то, что известно: у Instagram-объявлений нет коробки, топлива и т.п.
  const details = [
    listing.mileage !== undefined && formatMileage(listing.mileage),
    listing.transmission,
    listing.fuel,
  ].filter(Boolean);
  const place = listing.city ?? (listing.source && `@${listing.source.account}`);

  return (
    <Link
      href={`/cars/${listing.id}`}
      className="group flex flex-col overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200 transition hover:-translate-y-0.5 hover:shadow-md"
    >
      <div className="relative">
        <ListingPhoto
          listing={listing}
          sizes="(min-width: 1024px) 25vw, (min-width: 640px) 50vw, 100vw"
          className="transition group-hover:brightness-105"
        />
        {listing.source && (
          <span className="absolute top-2 left-2 rounded-full bg-gradient-to-r from-fuchsia-600 to-orange-500 px-2 py-0.5 text-xs font-semibold text-white shadow">
            Instagram
          </span>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-1 p-4">
        <p className="text-lg font-bold text-slate-900">
          {formatPrice(listing.price, listing.currency)}
          {listing.currency === "USD" && (
            <span className="ml-2 text-xs font-normal text-slate-400">
              ≈ {formatPrice(priceInSum(listing))}
            </span>
          )}
        </p>
        <h3 className="font-medium text-slate-800 group-hover:text-emerald-700">
          {listingTitle(listing)}
        </h3>
        {details.length > 0 && <p className="text-sm text-slate-500">{details.join(" · ")}</p>}
        <p className="mt-auto pt-2 text-xs text-slate-400">
          {[place, formatDate(listing.createdAt)].filter(Boolean).join(" · ")}
        </p>
      </div>
    </Link>
  );
}
