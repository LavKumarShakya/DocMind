"use client";

import { useState } from "react";
import { Send, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatInput({
  onSend,
  disabled = false,
  placeholder = "Ask a question about your documents...",
}: ChatInputProps) {
  const [value, setValue] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim() || disabled) return;
    onSend(value.trim());
    setValue("");
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-center gap-3 border-t border-[var(--edge)] bg-[var(--canvas-raised)] pt-4"
    >
      <Input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        maxLength={2000}
        className="flex-1"
      />
      <Button
        type="submit"
        variant="primary"
        disabled={!value.trim() || disabled}
        className="h-10 px-4"
      >
        {disabled ? (
          <Loader2
            className="h-4 w-4"
            style={{ animation: "spin 0.7s linear infinite" }}
            aria-hidden
          />
        ) : (
          <Send className="h-4 w-4" aria-hidden />
        )}
        <span className="hidden sm:inline ml-1.5">Ask</span>
      </Button>
    </form>
  );
}
