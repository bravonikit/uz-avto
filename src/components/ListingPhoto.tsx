// Фото объявления: настоящее, если есть, иначе нарисованная машинка.

import Image from "next/image";
import { CarPhoto } from "./CarPhoto";
import type { Listing } from "@/lib/listings";

type Props = {
  listing: Listing;
  sizes: string; // какой ширины будет фото на экране — чтобы не грузить лишнего
  priority?: boolean;
  className?: string;
};

export function ListingPhoto({ listing, sizes, priority, className = "" }: Props) {
  if (!listing.image) {
    return <CarPhoto listing={listing} className={`aspect-[16/10] ${className}`} />;
  }
  return (
    <div className={`relative aspect-[16/10] bg-slate-100 ${className}`}>
      <Image
        src={listing.image}
        alt={`${listing.brand} ${listing.model}`}
        fill
        sizes={sizes}
        priority={priority}
        className="object-cover"
      />
    </div>
  );
}
