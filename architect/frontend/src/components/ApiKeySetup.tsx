import { useState } from "react";
import { KeyRound, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { validateApiKey } from "../api/settings";
import { useAppDispatch } from "../context/AppContext";

type Status = "idle" | "validating" | "success" | "error";

export default function ApiKeySetup() {
  const dispatch = useAppDispatch();
  const [key, setKey] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [errorMsg, setErrorMsg] = useState("");

  const handleSubmit = async () => {
    if (!key.trim()) return;
    setStatus("validating");
    setErrorMsg("");

    try {
      const res = await validateApiKey(key.trim());
      if (res.valid) {
        setStatus("success");
        setTimeout(() => {
          dispatch({ type: "SET_API_KEY_CONFIGURED", payload: true });
        }, 800);
      } else {
        setStatus("error");
        setErrorMsg(res.message);
      }
    } catch (err) {
      setStatus("error");
      setErrorMsg(err instanceof Error ? err.message : "Connection failed.");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && status !== "validating") {
      handleSubmit();
    }
  };

  return (
    <div className="flex h-screen items-center justify-center bg-ds-bg-subtle">
      <div className="w-full max-w-[400px] rounded-[var(--radius-xl)] bg-ds-bg p-8 shadow-lg">
        {/* Icon */}
        <div className="mb-6 flex justify-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-ds-accent-subtle">
            <KeyRound size={22} className="text-ds-accent" />
          </div>
        </div>

        {/* Title */}
        <h1 className="mb-1 text-center text-lg font-semibold text-ds-text">
          Welcome to ARCHITECT
        </h1>
        <p className="mb-6 text-center text-[12px] text-ds-text-secondary">
          Enter your Anthropic API key to get started.
        </p>

        {/* Input */}
        <div className="mb-4">
          <input
            type="password"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="sk-ant-..."
            disabled={status === "validating" || status === "success"}
            className="w-full rounded-[var(--radius-md)] border border-ds-input-border bg-ds-input-bg px-3 py-2.5 text-[13px] text-ds-text placeholder:text-ds-text-tertiary focus:border-ds-input-focus focus:outline-none disabled:opacity-50"
          />
        </div>

        {/* Status message */}
        {status === "error" && (
          <div className="mb-4 flex items-center gap-2 rounded-[var(--radius-md)] bg-ds-error-subtle px-3 py-2 text-[12px] text-ds-error">
            <AlertCircle size={14} className="flex-shrink-0" />
            {errorMsg}
          </div>
        )}
        {status === "success" && (
          <div className="mb-4 flex items-center gap-2 rounded-[var(--radius-md)] bg-ds-success-subtle px-3 py-2 text-[12px] text-ds-success">
            <CheckCircle2 size={14} className="flex-shrink-0" />
            Connected successfully.
          </div>
        )}

        {/* Button */}
        <button
          onClick={handleSubmit}
          disabled={!key.trim() || status === "validating" || status === "success"}
          className="flex w-full items-center justify-center gap-2 rounded-[var(--radius-md)] bg-ds-accent px-4 py-2.5 text-[13px] font-medium text-ds-accent-text transition-colors hover:bg-ds-accent-hover disabled:opacity-40"
        >
          {status === "validating" ? (
            <>
              <Loader2 size={14} className="animate-spin" />
              Validating...
            </>
          ) : status === "success" ? (
            <>
              <CheckCircle2 size={14} />
              Connected
            </>
          ) : (
            "Connect"
          )}
        </button>

        {/* Help text */}
        <p className="mt-4 text-center text-[10px] leading-relaxed text-ds-text-tertiary">
          Your API key is stored locally and used only for direct
          communication with Anthropic's API.
        </p>
      </div>
    </div>
  );
}
