"use client";

import { useParams } from "next/navigation";

import { ChatView } from "@/components/chat/chat-view";

export function ChatRoute() {
  const { sessionId } = useParams<{ sessionId: string }>();
  // key: при переходе между диалогами состояние потока и выбора сбрасывается
  return <ChatView key={sessionId} sessionId={sessionId} />;
}
