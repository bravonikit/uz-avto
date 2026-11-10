"use client";
// Галерея: большое фото и миниатюры под ним. Клик по миниатюре меняет фото.

import { useState } from "react";
import { CarPhoto } from "./CarPhoto";
import type { Listing } from "@/lib/listings";

const VIEWS = [0, 1, 2];

export function Gallery({ listing }: { listing: Listing }) {
  const [active, setActive] = useState(0);

  return (
    <div>
      <div className="overflow-hidden rounded-2xl ring-1 ring-slate-200">
        <CarPhoto listing={listing} view={active} className="aspect-[16/10]" />
      </div>
      <div className="mt-3 grid grid-cols-3 gap-3">
        {VIEWS.map((view) => (
          <button
            key={view}
            type="button"
            onClick={() => setActive(view)}
            aria-label={`Фото ${view + 1}`}
            className={`overflow-hidden rounded-xl ring-2 transition ${
              active === view ? "ring-emerald-500" : "ring-transparent opacity-70 hover:opacity-100"
            }`}
          >
            <CarPhoto listing={listing} view={view} className="aspect-[16/10]" />
          </button>
        ))}
      </div>
    </div>
  );
}
