import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ChatPage } from "@/features/chat/ChatPage";

export default function Home() {
  return (
    <ErrorBoundary>
      <ChatPage />
    </ErrorBoundary>
  );
}
