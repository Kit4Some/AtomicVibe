interface ChatMessageProps {
  role: "assistant" | "user";
  content: string;
}

export default function ChatMessage({ role, content }: ChatMessageProps) {
  const isAssistant = role === "assistant";
  return (
    <div
      className={`flex ${isAssistant ? "justify-start" : "justify-end"} mb-3`}
    >
      <div
        className={`max-w-[80%] rounded-[var(--radius-xl)] px-4 py-3 text-[13px] leading-relaxed whitespace-pre-wrap ${
          isAssistant
            ? "bg-ds-accent-subtle text-ds-text rounded-bl-[var(--radius-sm)]"
            : "bg-ds-surface text-ds-text border border-ds-border rounded-br-[var(--radius-sm)]"
        }`}
      >
        {content}
      </div>
    </div>
  );
}
