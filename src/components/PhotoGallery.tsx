"use client";
// Галерея настоящих фото на странице машины: большое фото и лента миниатюр под ним.
// Клик по миниатюре делает её большой. Стрелки на большом фото и клавиши ← → листают.
// Клик по большому фото открывает его на весь экран (Esc или клик по фону закрывает).

import { useCallback, useEffect, useRef, useState } from "react";

type Props = {
  photos: string[]; // первое это обложка
  alt: string;
};

export function PhotoGallery({ photos, alt }: Props) {
  const [active, setActive] = useState(0);
  const [full, setFull] = useState(false);
  const strip = useRef<HTMLDivElement>(null);
  const many = photos.length > 1;

  const go = useCallback(
    (step: number) => setActive((current) => (current + step + photos.length) % photos.length),
    [photos.length],
  );

  // Активная миниатюра всегда видна в ленте
  useEffect(() => {
    strip.current?.children[active]?.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" });
  }, [active]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "ArrowLeft") go(-1);
      else if (event.key === "ArrowRight") go(1);
      else if (event.key === "Escape") setFull(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go]);

  // Пока открыт полный экран, страница под ним не прокручивается
  useEffect(() => {
    if (!full) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [full]);

  const arrows = (big: boolean) =>
    many && (
      <>
        <Arrow side="left" big={big} onClick={() => go(-1)} />
        <Arrow side="right" big={big} onClick={() => go(1)} />
      </>
    );

  return (
    <div>
      <div className="group relative aspect-[4/3] overflow-hidden rounded-2xl bg-slate-100 ring-1 ring-slate-200">
        <button type="button" onClick={() => setFull(true)} className="block h-full w-full cursor-zoom-in" aria-label="Открыть фото на весь экран">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img key={photos[active]} src={photos[active]} alt={alt} fetchPriority={active === 0 ? "high" : "auto"} className="h-full w-full animate-[fade_.2s_ease-out] object-contain" />
        </button>
        {arrows(false)}
        {many && (
          <span className="pointer-events-none absolute right-3 bottom-3 rounded-full bg-black/55 px-2.5 py-1 text-xs font-medium text-white">
            {active + 1} / {photos.length}
          </span>
        )}
      </div>

      {many && (
        <div ref={strip} className="mt-3 flex gap-2 overflow-x-auto pb-1">
          {photos.map((photo, index) => (
            <button
              key={photo}
              type="button"
              onClick={() => setActive(index)}
              aria-label={`Фото ${index + 1}`}
              aria-current={index === active}
              className={`relative aspect-[4/3] w-24 shrink-0 overflow-hidden rounded-lg transition sm:w-28 ${
                index === active ? "ring-2 ring-brand-600" : "opacity-60 ring-1 ring-slate-200 hover:opacity-100"
              }`}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={photo} alt="" loading="lazy" className="h-full w-full object-cover" />
            </button>
          ))}
        </div>
      )}

      {full && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4"
          onClick={() => setFull(false)}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            key={photos[active]}
            src={photos[active]}
            alt={alt}
            onClick={(event) => event.stopPropagation()}
            className="max-h-full max-w-full animate-[fade_.2s_ease-out] object-contain"
          />
          <div onClick={(event) => event.stopPropagation()}>{arrows(true)}</div>
          <button
            type="button"
            onClick={() => setFull(false)}
            aria-label="Закрыть"
            className="absolute top-4 right-4 flex h-11 w-11 items-center justify-center rounded-full bg-white/15 text-2xl text-white hover:bg-white/25"
          >
            ×
          </button>
          {many && (
            <span className="absolute bottom-5 left-1/2 -translate-x-1/2 rounded-full bg-white/15 px-3 py-1 text-sm text-white">
              {active + 1} / {photos.length}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function Arrow({ side, big, onClick }: { side: "left" | "right"; big: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={side === "left" ? "Предыдущее фото" : "Следующее фото"}
      className={`absolute top-1/2 -translate-y-1/2 ${side === "left" ? "left-3" : "right-3"} flex items-center justify-center rounded-full text-white transition ${
        big
          ? "h-12 w-12 bg-white/15 text-3xl hover:bg-white/25"
          : "h-10 w-10 bg-black/45 text-2xl opacity-0 group-hover:opacity-100 hover:bg-black/65 max-sm:opacity-100"
      }`}
    >
      {side === "left" ? "‹" : "›"}
    </button>
  );
}
