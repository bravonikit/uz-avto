// Карточка объявления в ленте: фото, цена, название, пробег, город.

import Link from "next/link";
import { CarPhoto } from "./CarPhoto";
import { formatDate, formatMileage, formatPrice } from "@/lib/format";
import type { Listing } from "@/lib/listings";

export function ListingCard({ listing }: { listing: Listing }) {
  return (
    <Link
      href={`/cars/${listing.id}`}
      className="group flex flex-col overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200 transition hover:-translate-y-0.5 hover:shadow-md"
    >
      <CarPhoto listing={listing} className="aspect-[16/10] transition group-hover:brightness-105" />
      <div className="flex flex-1 flex-col gap-1 p-4">
        <p className="text-lg font-bold text-slate-900">{formatPrice(listing.price)}</p>
        <h3 className="font-medium text-slate-800 group-hover:text-emerald-700">
          {listing.brand} {listing.model}, {listing.year}
        </h3>
        <p className="text-sm text-slate-500">
          {formatMileage(listing.mileage)} · {listing.transmission} · {listing.fuel}
        </p>
        <p className="mt-auto pt-2 text-xs text-slate-400">
          {listing.city} · {formatDate(listing.createdAt)}
        </p>
      </div>
    </Link>
  );
}
