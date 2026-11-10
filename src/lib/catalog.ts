// Справочники: марки с моделями, города, варианты характеристик.
// Используются и в поиске, и в форме подачи объявления.

export const BRANDS: Record<string, string[]> = {
  Chevrolet: ["Cobalt", "Nexia", "Gentra", "Spark", "Malibu", "Tracker", "Captiva", "Damas"],
  Kia: ["K5", "Sportage", "Sonet", "Seltos"],
  Hyundai: ["Elantra", "Sonata", "Tucson", "Creta"],
  BYD: ["Song Plus", "Chazor", "Han", "Seal"],
  Toyota: ["Camry", "Corolla", "RAV4", "Land Cruiser"],
  Lada: ["Vesta", "Granta", "Niva"],
};

export const BRAND_NAMES = Object.keys(BRANDS);

export const CITIES = [
  "Ташкент",
  "Самарканд",
  "Бухара",
  "Андижан",
  "Наманган",
  "Фергана",
  "Нукус",
  "Карши",
  "Навои",
  "Ургенч",
];

export const BODY_TYPES = ["Седан", "Хэтчбек", "Кроссовер", "Внедорожник", "Минивэн"] as const;
export const FUEL_TYPES = ["Бензин", "Газ/бензин", "Дизель", "Гибрид", "Электро"] as const;
export const TRANSMISSIONS = ["Механика", "Автомат"] as const;
export const DRIVES = ["Передний", "Задний", "Полный"] as const;

export const OLDEST_YEAR = 1990;
export const NEWEST_YEAR = 2026;

// Список годов от новых к старым: [2026, 2025, ..., 1990]
export const YEARS = Array.from(
  { length: NEWEST_YEAR - OLDEST_YEAR + 1 },
  (_, i) => NEWEST_YEAR - i,
);
