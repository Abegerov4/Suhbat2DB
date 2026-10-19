import type { Metadata } from "next";

export const metadata: Metadata = {
  title: { default: "Источники данных", template: "%s · Suhbat2DB" },
};

export default function DatasourcesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
