import type { Choice } from "../api/types";

interface ChoiceSelectorProps {
  choices: Choice[];
  onSelect: (id: string) => void;
}

export default function ChoiceSelector({
  choices,
  onSelect,
}: ChoiceSelectorProps) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {choices.map((choice) => (
        <button
          key={choice.id}
          onClick={() => onSelect(choice.id)}
          className={`group relative rounded-[var(--radius-xl)] border p-4 text-left transition-all hover:scale-[1.02] ${
            choice.recommended
              ? "border-ds-accent bg-ds-accent-subtle hover:brightness-110"
              : "border-ds-border bg-ds-surface hover:bg-ds-surface-hover"
          }`}
        >
          {choice.recommended && (
            <span className="absolute -top-2 right-3 rounded-full bg-ds-accent px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-ds-accent-text">
              Recommended
            </span>
          )}
          <div className="mb-1 flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-ds-surface-hover text-xs font-bold text-ds-text-secondary">
              {choice.id}
            </span>
            <span className="font-semibold text-ds-text">{choice.label}</span>
          </div>
          <p className="mb-2 text-xs text-ds-text-secondary">{choice.description}</p>
          <div className="space-y-1 text-[11px]">
            {choice.pros.length > 0 && (
              <div className="text-ds-success">
                + {choice.pros.join(" / ")}
              </div>
            )}
            {choice.cons.length > 0 && (
              <div className="text-ds-error">
                - {choice.cons.join(" / ")}
              </div>
            )}
          </div>
        </button>
      ))}
    </div>
  );
}
