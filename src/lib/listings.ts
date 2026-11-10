// Тестовые объявления. Позже этот файл заменится запросами к базе данных,
// а остальной код почти не изменится: страницы зовут только функции ниже.

import type { BODY_TYPES, DRIVES, FUEL_TYPES, TRANSMISSIONS } from "./catalog";
import { parseNumber } from "./format";

export type Listing = {
  id: string;
  brand: string;
  model: string;
  year: number;
  price: number; // в сумах
  mileage: number; // в километрах
  city: string;
  bodyType: (typeof BODY_TYPES)[number];
  engine: string;
  fuel: (typeof FUEL_TYPES)[number];
  transmission: (typeof TRANSMISSIONS)[number];
  drive: (typeof DRIVES)[number];
  color: { name: string; hex: string };
  description: string;
  seller: { name: string; phone: string; type: "Частное лицо" | "Автосалон" };
  createdAt: string;
};

const LISTINGS: Listing[] = [
  {
    id: "1001",
    brand: "Chevrolet",
    model: "Cobalt",
    year: 2023,
    price: 155_000_000,
    mileage: 28_000,
    city: "Ташкент",
    bodyType: "Седан",
    engine: "1.5 л, 106 л.с.",
    fuel: "Бензин",
    transmission: "Автомат",
    drive: "Передний",
    color: { name: "Белый", hex: "#f1f5f9" },
    description:
      "Один хозяин, обслуживание у официального дилера. Не бит, не крашен. Зимняя резина в подарок.",
    seller: { name: "Азиз", phone: "+998 90 123-45-67", type: "Частное лицо" },
    createdAt: "2026-11-09",
  },
  {
    id: "1002",
    brand: "Chevrolet",
    model: "Nexia",
    year: 2019,
    price: 98_000_000,
    mileage: 96_000,
    city: "Самарканд",
    bodyType: "Седан",
    engine: "1.5 л, 107 л.с.",
    fuel: "Газ/бензин",
    transmission: "Механика",
    drive: "Передний",
    color: { name: "Серебристый", hex: "#cbd5e1" },
    description: "Стоит газ (метан), экономичная. Кондиционер работает, ходовая в порядке.",
    seller: { name: "Шерзод", phone: "+998 93 555-12-34", type: "Частное лицо" },
    createdAt: "2026-11-08",
  },
  {
    id: "1003",
    brand: "Chevrolet",
    model: "Malibu",
    year: 2022,
    price: 330_000_000,
    mileage: 41_000,
    city: "Ташкент",
    bodyType: "Седан",
    engine: "2.0 л, 250 л.с.",
    fuel: "Бензин",
    transmission: "Автомат",
    drive: "Передний",
    color: { name: "Чёрный", hex: "#1e293b" },
    description: "Комплектация Premier: кожаный салон, панорама, камера 360. Состояние отличное.",
    seller: { name: "AutoCity Tashkent", phone: "+998 71 200-00-01", type: "Автосалон" },
    createdAt: "2026-11-10",
  },
  {
    id: "1004",
    brand: "Chevrolet",
    model: "Tracker",
    year: 2024,
    price: 262_000_000,
    mileage: 9_000,
    city: "Ташкент",
    bodyType: "Кроссовер",
    engine: "1.2 л турбо, 132 л.с.",
    fuel: "Бензин",
    transmission: "Автомат",
    drive: "Передний",
    color: { name: "Красный", hex: "#dc2626" },
    description: "Почти новый, на гарантии. Тонировка и защитная плёнка на капоте.",
    seller: { name: "Дилноза", phone: "+998 97 777-88-99", type: "Частное лицо" },
    createdAt: "2026-11-07",
  },
  {
    id: "1005",
    brand: "Chevrolet",
    model: "Spark",
    year: 2021,
    price: 82_000_000,
    mileage: 54_000,
    city: "Фергана",
    bodyType: "Хэтчбек",
    engine: "1.25 л, 85 л.с.",
    fuel: "Бензин",
    transmission: "Автомат",
    drive: "Передний",
    color: { name: "Голубой", hex: "#38bdf8" },
    description: "Отличный городской автомобиль, по городу расход 6 л. Вложений не требует.",
    seller: { name: "Малика", phone: "+998 91 333-22-11", type: "Частное лицо" },
    createdAt: "2026-11-06",
  },
  {
    id: "1006",
    brand: "Chevrolet",
    model: "Gentra",
    year: 2022,
    price: 142_000_000,
    mileage: 47_000,
    city: "Андижан",
    bodyType: "Седан",
    engine: "1.5 л, 107 л.с.",
    fuel: "Бензин",
    transmission: "Автомат",
    drive: "Передний",
    color: { name: "Серый", hex: "#64748b" },
    description: "Комплектация 3 позиция. Все ТО вовремя, сервисная книжка.",
    seller: { name: "Бобур", phone: "+998 94 100-20-30", type: "Частное лицо" },
    createdAt: "2026-11-05",
  },
  {
    id: "1007",
    brand: "Chevrolet",
    model: "Damas",
    year: 2020,
    price: 68_000_000,
    mileage: 120_000,
    city: "Наманган",
    bodyType: "Минивэн",
    engine: "0.8 л, 38 л.с.",
    fuel: "Газ/бензин",
    transmission: "Механика",
    drive: "Задний",
    color: { name: "Белый", hex: "#f8fafc" },
    description: "Рабочая лошадка, 7 мест. Пропан + бензин. Документы в порядке.",
    seller: { name: "Улугбек", phone: "+998 99 444-55-66", type: "Частное лицо" },
    createdAt: "2026-11-04",
  },
  {
    id: "1008",
    brand: "Kia",
    model: "K5",
    year: 2023,
    price: 385_000_000,
    mileage: 22_000,
    city: "Ташкент",
    bodyType: "Седан",
    engine: "2.5 л, 194 л.с.",
    fuel: "Бензин",
    transmission: "Автомат",
    drive: "Передний",
    color: { name: "Синий", hex: "#1d4ed8" },
    description: "GT-Line, полный фарш. Куплен в салоне в Ташкенте, один владелец.",
    seller: { name: "Kia Center Chilonzor", phone: "+998 71 300-40-50", type: "Автосалон" },
    createdAt: "2026-11-09",
  },
  {
    id: "1009",
    brand: "Kia",
    model: "Sportage",
    year: 2022,
    price: 415_000_000,
    mileage: 38_000,
    city: "Бухара",
    bodyType: "Кроссовер",
    engine: "2.0 л, 150 л.с.",
    fuel: "Бензин",
    transmission: "Автомат",
    drive: "Полный",
    color: { name: "Зелёный", hex: "#166534" },
    description: "Полный привод, подогрев всех сидений и руля. Обмен не интересует.",
    seller: { name: "Фаррух", phone: "+998 90 987-65-43", type: "Частное лицо" },
    createdAt: "2026-11-03",
  },
  {
    id: "1010",
    brand: "Hyundai",
    model: "Elantra",
    year: 2021,
    price: 295_000_000,
    mileage: 63_000,
    city: "Ташкент",
    bodyType: "Седан",
    engine: "2.0 л, 150 л.с.",
    fuel: "Бензин",
    transmission: "Автомат",
    drive: "Передний",
    color: { name: "Серебристый", hex: "#e2e8f0" },
    description: "Ухоженный автомобиль, гаражное хранение. Возможен торг у машины.",
    seller: { name: "Рустам", phone: "+998 93 222-33-44", type: "Частное лицо" },
    createdAt: "2026-11-02",
  },
  {
    id: "1011",
    brand: "BYD",
    model: "Song Plus",
    year: 2024,
    price: 425_000_000,
    mileage: 12_000,
    city: "Ташкент",
    bodyType: "Кроссовер",
    engine: "1.5 л + электромотор",
    fuel: "Гибрид",
    transmission: "Автомат",
    drive: "Передний",
    color: { name: "Серый", hex: "#475569" },
    description: "Подключаемый гибрид DM-i: по городу почти без бензина. Зарядка в комплекте.",
    seller: { name: "EV Motors", phone: "+998 71 500-60-70", type: "Автосалон" },
    createdAt: "2026-11-10",
  },
  {
    id: "1012",
    brand: "BYD",
    model: "Chazor",
    year: 2024,
    price: 318_000_000,
    mileage: 5_000,
    city: "Самарканд",
    bodyType: "Седан",
    engine: "1.5 л + электромотор",
    fuel: "Гибрид",
    transmission: "Автомат",
    drive: "Передний",
    color: { name: "Белый", hex: "#f1f5f9" },
    description: "Узбекская сборка, на гарантии. Пробег минимальный, как новый.",
    seller: { name: "Жасур", phone: "+998 95 111-00-99", type: "Частное лицо" },
    createdAt: "2026-11-08",
  },
  {
    id: "1013",
    brand: "Toyota",
    model: "Camry",
    year: 2020,
    price: 410_000_000,
    mileage: 88_000,
    city: "Ташкент",
    bodyType: "Седан",
    engine: "2.5 л, 181 л.с.",
    fuel: "Бензин",
    transmission: "Автомат",
    drive: "Передний",
    color: { name: "Чёрный", hex: "#0f172a" },
    description: "Camry 70, комплектация Prestige. Без ДТП, родная краска.",
    seller: { name: "Отабек", phone: "+998 90 600-70-80", type: "Частное лицо" },
    createdAt: "2026-11-01",
  },
  {
    id: "1014",
    brand: "Toyota",
    model: "Land Cruiser",
    year: 2022,
    price: 1_290_000_000,
    mileage: 34_000,
    city: "Ташкент",
    bodyType: "Внедорожник",
    engine: "3.5 л турбо, 415 л.с.",
    fuel: "Бензин",
    transmission: "Автомат",
    drive: "Полный",
    color: { name: "Белый перламутр", hex: "#fafaf9" },
    description: "Land Cruiser 300, максимальная комплектация. Полностью обслужен у дилера.",
    seller: { name: "Premium Auto", phone: "+998 71 900-10-20", type: "Автосалон" },
    createdAt: "2026-11-09",
  },
  {
    id: "1015",
    brand: "Lada",
    model: "Vesta",
    year: 2021,
    price: 128_000_000,
    mileage: 59_000,
    city: "Нукус",
    bodyType: "Седан",
    engine: "1.6 л, 106 л.с.",
    fuel: "Бензин",
    transmission: "Механика",
    drive: "Передний",
    color: { name: "Оранжевый", hex: "#ea580c" },
    description: "Надёжная, недорогая в обслуживании. Новая резина и аккумулятор.",
    seller: { name: "Алишер", phone: "+998 88 123-12-12", type: "Частное лицо" },
    createdAt: "2026-10-31",
  },
];

// Что может прийти из поисковой формы (все поля необязательные).
export type ListingFilters = {
  brand?: string;
  model?: string;
  city?: string;
  priceFrom?: number;
  priceTo?: number;
  yearFrom?: number;
  yearTo?: number;
  sort?: "new" | "cheap" | "expensive";
};

// Превращает параметры из адреса (?brand=Kia&priceTo=300000000) в фильтры.
export function filtersFromSearchParams(
  params: Record<string, string | string[] | undefined>,
): ListingFilters {
  const text = (key: string) => {
    const value = params[key];
    return typeof value === "string" && value.trim() ? value.trim() : undefined;
  };
  const sort = text("sort");
  return {
    brand: text("brand"),
    model: text("model"),
    city: text("city"),
    priceFrom: parseNumber(params.priceFrom),
    priceTo: parseNumber(params.priceTo),
    yearFrom: parseNumber(params.yearFrom),
    yearTo: parseNumber(params.yearTo),
    sort: sort === "cheap" || sort === "expensive" ? sort : "new",
  };
}

export function searchListings(filters: ListingFilters = {}): Listing[] {
  const found = LISTINGS.filter(
    (car) =>
      (!filters.brand || car.brand === filters.brand) &&
      (!filters.model || car.model === filters.model) &&
      (!filters.city || car.city === filters.city) &&
      (filters.priceFrom === undefined || car.price >= filters.priceFrom) &&
      (filters.priceTo === undefined || car.price <= filters.priceTo) &&
      (filters.yearFrom === undefined || car.year >= filters.yearFrom) &&
      (filters.yearTo === undefined || car.year <= filters.yearTo),
  );

  return found.sort((a, b) => {
    if (filters.sort === "cheap") return a.price - b.price;
    if (filters.sort === "expensive") return b.price - a.price;
    return b.createdAt.localeCompare(a.createdAt);
  });
}

export function getListing(id: string): Listing | undefined {
  return LISTINGS.find((car) => car.id === id);
}

export function getAllListingIds(): string[] {
  return LISTINGS.map((car) => car.id);
}
