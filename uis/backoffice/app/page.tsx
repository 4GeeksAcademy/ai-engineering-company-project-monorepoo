import type { BrasalandBusinessInput } from "@repo/shared-types";
import Dashboard from "@/components/Dashboard";

const sampleInput: BrasalandBusinessInput = {
  weekLabel: "Semana 31 - 2026",
  sales: [
    {
      storeId: "co-med-01",
      storeName: "Brasaland El Poblado",
      country: "CO",
      currency: "COP",
      orders: 1120,
      revenue: 179_200_000,
      averageTicket: 160_000,
    },
    {
      storeId: "co-bog-01",
      storeName: "Brasaland Zona T",
      country: "CO",
      currency: "COP",
      orders: 990,
      revenue: 145_530_000,
      averageTicket: 147_000,
    },
    {
      storeId: "us-mia-01",
      storeName: "Brasaland Doral",
      country: "US",
      currency: "USD",
      orders: 780,
      revenue: 45_240,
      averageTicket: 58,
    },
  ],
  inventory: [
    {
      storeId: "co-med-01",
      storeName: "Brasaland El Poblado",
      ingredient: "Pechuga marinada",
      availableUnits: 70,
      estimatedWeeklyDemand: 92,
    },
    {
      storeId: "us-mia-01",
      storeName: "Brasaland Doral",
      ingredient: "Costilla premium",
      availableUnits: 64,
      estimatedWeeklyDemand: 60,
    },
  ],
  suppliers: [
    {
      supplierName: "Carnes Andinas",
      category: "Proteinas",
      priceChangePct: 8.5,
    },
    {
      supplierName: "Fresh Citrus FL",
      category: "Bebidas",
      priceChangePct: 3.2,
    },
  ],
  hr: [
    {
      country: "CO",
      turnoverPct: 16,
      absenteeismPct: 6,
      daysToFillVacancy: 34,
    },
    {
      country: "US",
      turnoverPct: 21,
      absenteeismPct: 8,
      daysToFillVacancy: 43,
    },
  ],
};

export default function Home() {
  return <Dashboard input={sampleInput} />;
}
