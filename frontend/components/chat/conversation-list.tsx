"use client";

import { Plus, Trash2, Loader2, MessageSquare } from "lucide-react";
import { useState } from "react";
import { type ConversationSummary } from "@/lib/conversations";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { cn } from "@/lib/utils";

interface ConversationListProps {
  conversations: ConversationSummary[];
  activeId: string | null;
  loading?: boolean;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => Promise<void>;
}

export function ConversationList({
  conversations,
  activeId,
  loading = false,
  onSelect,
  onNew,
  onDelete,
}: ConversationListProps) {
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deletingTitle, setDeletingTitle] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deletePending, setDeletePending] = useState(false);

  const handleDeleteClick = (e: React.MouseEvent, id: string, title: string) => {
    e.stopPropagation();
    setDeletingId(id);
    setDeletingTitle(title);
    setConfirmOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!deletingId) return;
    setDeletePending(true);
    try {
      await onDelete(deletingId);
    } finally {
      setDeletePending(false);
      setConfirmOpen(false);
      setDeletingId(null);
      setDeletingTitle("");
    }
  };

  return (
    <div className="flex flex-col h-full bg-[var(--canvas-raised)]">
      {/* Action Header */}
      <div className="p-4 border-b border-[var(--edge)]">
        <button
          type="button"
          onClick={onNew}
          className="flex w-full items-center justify-center gap-2 rounded-[var(--radius-sm)] bg-[var(--ink)] py-2 text-sm font-semibold text-[var(--canvas)] hover:bg-[var(--ink-muted)] transition-colors"
        >
          <Plus className="h-4 w-4" aria-hidden />
          <span>New Chat</span>
        </button>
      </div>

      {/* Conversations List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1">
        <span className="block px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-[var(--ink-ghost)]">
          History
        </span>

        {loading && (
          <div className="flex items-center justify-center gap-2 py-8 text-xs text-[var(--ink-faint)]">
            <Loader2
              className="h-4 w-4 text-[var(--primary)]"
              style={{ animation: "spin 0.7s linear infinite" }}
              aria-hidden
            />
            <span>Loading chats…</span>
          </div>
        )}

        {!loading && conversations.length === 0 && (
          <p className="py-8 text-center text-xs text-[var(--ink-ghost)]">
            No chats yet.
          </p>
        )}

        {!loading &&
          conversations.map((convo) => {
            const isActive = convo.id === activeId;
            return (
              <div
                key={convo.id}
                onClick={() => onSelect(convo.id)}
                className={cn(
                  "group flex items-center justify-between rounded-[var(--radius-sm)] px-3 py-2 cursor-pointer transition-all duration-150",
                  isActive
                    ? "bg-[var(--primary-faint)] text-[var(--primary)] font-semibold"
                    : "text-[var(--ink-muted)] hover:bg-[var(--canvas-inset)] hover:text-[var(--ink)]"
                )}
              >
                <div className="flex min-w-0 flex-1 items-center gap-2.5">
                  <MessageSquare className="h-4 w-4 shrink-0" aria-hidden />
                  <span className="truncate text-sm">{convo.title}</span>
                </div>
                <button
                  type="button"
                  onClick={(e) => handleDeleteClick(e, convo.id, convo.title)}
                  className="opacity-0 group-hover:opacity-100 p-0.5 rounded text-[var(--ink-ghost)] hover:text-[var(--danger)] hover:bg-[var(--canvas-raised)] transition-all"
                  aria-label={`Delete chat ${convo.title}`}
                >
                  <Trash2 className="h-3.5 w-3.5" aria-hidden />
                </button>
              </div>
            );
          })}
      </div>

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={confirmOpen}
        title="Delete chat?"
        description={`This will permanently delete the conversation "${deletingTitle}" and all of its messages.`}
        confirmLabel="Delete"
        loading={deletePending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
}
