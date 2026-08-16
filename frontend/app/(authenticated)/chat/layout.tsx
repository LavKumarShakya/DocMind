"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import { Menu, X } from "lucide-react";
import { ConversationList } from "@/components/chat/conversation-list";
import { listConversations, deleteConversation, type ConversationSummary } from "@/lib/conversations";
import { useToast } from "@/components/common/toast";
import { cn } from "@/lib/utils";

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const params = useParams();
  const { toast } = useToast();

  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const activeId = (params?.id as string) || null;

  const fetchConversations = useCallback(async () => {
    try {
      const list = await listConversations();
      setConversations(list);
    } catch {
      toast("Unable to load chat history.", "error");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void fetchConversations();
  }, [fetchConversations]);

  const handleSelect = (id: string) => {
    router.push(`/chat/${id}`);
    setSidebarOpen(false);
  };

  const handleNew = () => {
    router.push("/chat");
    setSidebarOpen(false);
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteConversation(id);
      toast("Chat conversation deleted.", "success");
      if (activeId === id) {
        router.push("/chat");
      }
      await fetchConversations();
    } catch {
      toast("Failed to delete chat.", "error");
    }
  };

  return (
    <div className="flex h-[calc(100vh-56px)] overflow-hidden bg-[var(--canvas)]">
      {/* Desktop History Sidebar */}
      <aside className="hidden md:block w-72 shrink-0 border-r border-[var(--edge)] bg-[var(--canvas-raised)]">
        <ConversationList
          conversations={conversations}
          activeId={activeId}
          loading={loading}
          onSelect={handleSelect}
          onNew={handleNew}
          onDelete={handleDelete}
        />
      </aside>

      {/* Mobile History Sidebar Overlay */}
      {sidebarOpen && (
        <>
          <div
            className="fixed inset-0 z-40 bg-[var(--ink)]/30 md:hidden"
            onClick={() => setSidebarOpen(false)}
            aria-hidden
          />
          <div
            className="fixed inset-y-0 left-0 z-50 w-72 bg-[var(--canvas-raised)] md:hidden shadow-[var(--shadow-lg)]"
            style={{ animation: "slide-in-bottom 0.2s ease-out" }}
          >
            <div className="flex justify-end p-2 border-b border-[var(--edge)]">
              <button
                type="button"
                onClick={() => setSidebarOpen(false)}
                className="p-1 rounded-[var(--radius-sm)] text-[var(--ink-ghost)] hover:bg-[var(--canvas-inset)] hover:text-[var(--ink)]"
                aria-label="Close menu"
              >
                <X className="h-5 w-5" aria-hidden />
              </button>
            </div>
            <div className="h-[calc(100%-49px)]">
              <ConversationList
                conversations={conversations}
                activeId={activeId}
                loading={loading}
                onSelect={handleSelect}
                onNew={handleNew}
                onDelete={handleDelete}
              />
            </div>
          </div>
        </>
      )}

      {/* Main Chat Panel Area */}
      <div className="flex flex-col min-w-0 flex-1 relative bg-[var(--canvas)]">
        {/* Mobile History Toggle Header */}
        <div className="flex md:hidden items-center justify-between border-b border-[var(--edge)] px-4 py-3 bg-[var(--canvas-raised)] shrink-0">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="flex items-center gap-1.5 text-xs font-semibold text-[var(--primary)]"
          >
            <Menu className="h-4 w-4" aria-hidden />
            <span>Chat History</span>
          </button>
        </div>

        {/* Dynamic page content */}
        <div className="flex-1 overflow-hidden">
          {children}
        </div>
      </div>
    </div>
  );
}
export { ChatLayout };
export const dynamic = "force-dynamic";
