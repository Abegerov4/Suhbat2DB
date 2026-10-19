import type { Metadata } from "next";

export const metadata: Metadata = {
  title: { default: "Новый диалог", template: "%s · Suhbat2DB" },
};

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
