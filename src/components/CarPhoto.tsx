// Временная «фотография» машины: рисунок SVG в цвет автомобиля.
// Когда появится хранилище файлов, здесь будет настоящее фото.

import type { Listing } from "@/lib/listings";

const BACKGROUNDS = [
  ["#e0f2fe", "#bae6fd"], // утро
  ["#fef3c7", "#fde68a"], // день
  ["#ede9fe", "#c4b5fd"], // вечер
];

type Props = {
  listing: Pick<Listing, "bodyType" | "color" | "brand" | "model">;
  view?: number; // 0, 1, 2 — разные «ракурсы» для галереи
  className?: string;
};

export function CarPhoto({ listing, view = 0, className = "" }: Props) {
  const [bgFrom, bgTo] = BACKGROUNDS[view % BACKGROUNDS.length];
  const tall = ["Кроссовер", "Внедорожник", "Минивэн"].includes(listing.bodyType ?? "");
  const carColor = listing.color?.hex ?? "#94a3b8";
  const gradientId = `bg-${view}`;

  return (
    <svg
      viewBox="0 0 320 200"
      role="img"
      aria-label={`${listing.brand} ${listing.model}`}
      className={`block w-full ${className}`}
      preserveAspectRatio="xMidYMid slice"
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={bgFrom} />
          <stop offset="1" stopColor={bgTo} />
        </linearGradient>
      </defs>
      <rect width="320" height="200" fill={`url(#${gradientId})`} />
      <rect y="160" width="320" height="40" fill="#94a3b8" opacity="0.35" />

      {/* Второй ракурс — машина развёрнута в другую сторону */}
      <g transform={view === 1 ? "translate(320 0) scale(-1 1)" : undefined}>
        <ellipse cx="160" cy="162" rx="135" ry="8" fill="#0f172a" opacity="0.15" />
        {tall ? (
          <>
            <path
              d="M28 150 L30 118 Q34 104 58 100 L92 96 L112 62 Q118 52 134 52 L238 52 Q254 52 262 64 L280 96 Q298 100 298 116 L298 150 Z"
              fill={carColor}
              stroke="#0f172a"
              strokeOpacity="0.25"
              strokeWidth="2"
            />
            <path d="M104 96 L120 64 L172 64 L172 96 Z" fill="#0f172a" opacity="0.55" />
            <path d="M180 96 L180 64 L236 64 Q246 64 252 74 L264 96 Z" fill="#0f172a" opacity="0.55" />
          </>
        ) : (
          <>
            <path
              d="M24 148 L30 124 Q38 110 66 106 L104 102 L136 76 Q148 68 166 68 L214 68 Q232 68 244 80 L268 104 L284 108 Q300 112 300 128 L300 148 Z"
              fill={carColor}
              stroke="#0f172a"
              strokeOpacity="0.25"
              strokeWidth="2"
            />
            <path d="M116 102 L142 80 L186 80 L186 102 Z" fill="#0f172a" opacity="0.55" />
            <path d="M194 102 L194 80 L216 80 Q228 80 236 88 L250 102 Z" fill="#0f172a" opacity="0.55" />
          </>
        )}
        <rect x="286" y="122" width="12" height="7" rx="2" fill="#fde047" />
        {[82, 242].map((cx) => (
          <g key={cx}>
            <circle cx={cx} cy="150" r="22" fill="#1e293b" />
            <circle cx={cx} cy="150" r="10" fill="#cbd5e1" />
          </g>
        ))}
      </g>
    </svg>
  );
}
