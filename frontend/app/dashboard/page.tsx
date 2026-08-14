"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  FileText,
  Loader2,
  MessageSquareText,
  Plus,
  RefreshCw,
  Search,
  Send,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  TriangleAlert,
  Upload,
} from "lucide-react";

import { RequireAuth } from "@/components/require-auth";
import { SiteHeader } from "@/components/site-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { type Citation, askQuestion } from "@/lib/chat";
import {
  type ConversationSummary,
  deleteConversation,
  getConversation,
  listConversations,
  type MessageDetail,
} from "@/lib/conversations";
import {
  type CampusDocument,
  type DocumentStatus,
  type DocumentVersion,
  deleteDocument,
  formatDate,
  formatFileSize,
  listDocuments,
  listVersions,
  processDocument,
  uploadDocument,
  uploadVersion,
} from "@/lib/documents";
import { submitFeedback } from "@/lib/feedback";
import { cn } from "@/lib/utils";

const statusStyles: Record<DocumentStatus, string> = {
  UPLOADED: "bg-blue-50 text-blue-700 border-blue-200",
  PROCESSING: "bg-amber-50 text-amber-700 border-amber-200",
  ACTIVE: "bg-emerald-50 text-emerald-700 border-emerald-200",
  FAILED: "bg-red-50 text-red-700 border-red-200",
  ARCHIVED: "bg-zinc-100 text-zinc-600 border-zinc-200",
};

function StatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        statusStyles[status],
      )}
    >
      {status === "PROCESSING" ? "Processing" : status.charAt(0) + status.slice(1).toLowerCase()}
    </span>
  );
}

function CitationList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;
  return (
    <div className="mt-3 border-t border-zinc-100 pt-2">
      <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-zinc-400">
        Sources ({citations.length})
      </p>
      <ul className="space-y-1.5">
        {citations.map((citation, i) => {
          const label =
            citation.section ??
            (citation.page_number != null ? `p. ${citation.page_number}` : null);
          return (
            <li key={`${citation.chunk_id}-${i}`} className="text-xs text-zinc-600">
              <span className="font-medium text-zinc-800">
                {citation.document_title}
              </span>
              {label && <span className="text-zinc-400"> · {label}</span>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function FeedbackButtons({ messageId }: { messageId: string }) {
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState<number | null>(null);

  async function rate(rating: number) {
    if (sending || sent !== null) return;
    setSending(true);
    try {
      await submitFeedback({ message_id: messageId, rating });
      setSent(rating);
    } catch {
      // non-fatal; ignore submission errors in the UI
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="mt-2 flex items-center gap-2 text-xs text-zinc-400">
      <span className="uppercase tracking-wide">Was this helpful?</span>
      <button
        type="button"
        onClick={() => rate(5)}
        disabled={sending || sent !== null}
        className={cn(
          "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 transition-colors",
          sent === 5
            ? "border-emerald-300 bg-emerald-50 text-emerald-700"
            : "border-zinc-200 hover:bg-zinc-50",
        )}
        aria-label="Helpful"
      >
        <ThumbsUp className="h-3.5 w-3.5" aria-hidden />
      </button>
      <button
        type="button"
        onClick={() => rate(1)}
        disabled={sending || sent !== null}
        className={cn(
          "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 transition-colors",
          sent === 1
            ? "border-red-300 bg-red-50 text-red-700"
            : "border-zinc-200 hover:bg-zinc-50",
        )}
        aria-label="Not helpful"
      >
        <ThumbsDown className="h-3.5 w-3.5" aria-hidden />
      </button>
    </div>
  );
}

function ConversationThread({
  messages,
  asking,
}: {
  messages: MessageDetail[];
  asking: boolean;
}) {
  return (
    <div className="space-y-4">
      {messages.length === 0 && !asking && (
        <p className="rounded-lg border border-dashed border-zinc-300 p-6 text-center text-sm text-zinc-500">
          Ask a question to start this conversation.
        </p>
      )}
      {messages.map((message) => (
        <div
          key={message.id}
          className={cn(
            "rounded-lg border p-4",
            message.role === "USER"
              ? "border-indigo-200 bg-indigo-50/60"
              : "border-zinc-100 bg-zinc-50",
          )}
        >
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-400">
            {message.role === "USER" ? "You" : "CampusRAG"}
          </p>
          <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-zinc-800">
            {message.content
              .replace(/\s*Sources:\s*\[[\d,\s]+\]\s*$/, "")
              .trim()}
          </p>
          {message.role === "ASSISTANT" && (
            <>
              <CitationList
                citations={(message.citations ?? []).map((c) => ({
                  chunk_id: c.chunk_id ?? "",
                  document_id: c.document_id ?? "",
                  document_title: c.document_title ?? "Unknown source",
                  page_number: c.page_number,
                  section: c.section,
                  chunk_index: 0,
                  relevance_score: c.relevance_score,
                }))}
              />
              <FeedbackButtons messageId={message.id} />
            </>
          )}
        </div>
      ))}
      {asking && (
        <div className="flex items-center gap-2 text-sm text-zinc-500" role="status">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          CampusRAG is searching your documents…
        </div>
      )}
    </div>
  );
}

function ChatPanel({
  conversationId,
  messages,
  setMessages,
  asking,
  ask,
  chatError,
}: {
  conversationId: string | null;
  messages: MessageDetail[];
  setMessages: (m: MessageDetail[]) => void;
  asking: boolean;
  ask: (question: string) => Promise<void>;
  chatError: string | null;
}) {
  const [question, setQuestion] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, asking]);

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || asking) return;
    setQuestion("");
    try {
      await ask(trimmed);
    } catch {
      setQuestion(trimmed);
    }
  }

  return (
    <section className="flex flex-col rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
      <div className="flex items-center gap-2">
        <MessageSquareText className="h-4 w-4 text-zinc-500" aria-hidden />
        <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500">
          Ask an academic question
        </h2>
      </div>
      <p className="mt-1 text-sm text-zinc-500">
        Answers are grounded in the documents you can view.
      </p>

      <div className="mt-4 space-y-4">
        <ConversationThread messages={messages} asking={asking} />
        <div ref={bottomRef} />
      </div>

      {chatError && <Alert className="mt-4" variant="error">{chatError}</Alert>}

      <form onSubmit={handleAsk} className="mt-4 flex items-center gap-3 border-t border-zinc-100 pt-4">
        <Input
          className="flex-1"
          placeholder={conversationId ? "Follow-up question…" : "e.g. What is the attendance policy?"}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={asking}
          maxLength={2000}
        />
        <Button type="submit" disabled={!question.trim() || asking} className="self-end">
          {asking ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          ) : (
            <Send className="h-4 w-4" aria-hidden />
          )}
          Ask
        </Button>
      </form>
    </section>
  );
}

function VersionHistory({ docId }: { docId: string }) {
  const [versions, setVersions] = useState<DocumentVersion[]>([]);
  const [state, setState] = useState<"loading" | "ready">("loading");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      setVersions(await listVersions(docId));
      setState("ready");
    } catch {
      setState("ready");
    }
  }, [docId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setUploading(true);
    try {
      await uploadVersion(docId, file);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  if (state === "loading") {
    return (
      <div className="flex items-center gap-2 text-xs text-zinc-500">
        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
        Loading versions…
      </div>
    );
  }

  return (
    <div className="mt-3 border-t border-zinc-100 pt-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-zinc-400">
          Versions ({versions.length})
        </p>
        <label className="cursor-pointer text-xs font-medium text-indigo-600 hover:underline">
          {uploading ? "Uploading…" : "Upload new version"}
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,application/pdf"
            className="sr-only"
            onChange={handleUpload}
            disabled={uploading}
          />
        </label>
      </div>
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
      {versions.length > 0 && (
        <ul className="mt-2 space-y-1.5">
          {versions.map((version) => (
            <li
              key={version.id}
              className="flex items-center justify-between rounded-lg border border-zinc-100 bg-zinc-50 px-3 py-1.5 text-xs"
            >
              <span className="truncate text-zinc-700">
                v{version.version_number} · {version.filename} ·{" "}
                {formatFileSize(version.file_size)}
                {version.page_count != null &&
                  ` · ${version.page_count} page${version.page_count === 1 ? "" : "s"}`}
              </span>
              <StatusBadge status={version.status} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function DashboardShell() {
  const { user } = useAuth();

  const [documents, setDocuments] = useState<CampusDocument[]>([]);
  const [listState, setListState] = useState<"loading" | "ready" | "error">("loading");
  const [listError, setListError] = useState<string | null>(null);
  const [expandedVersions, setExpandedVersions] = useState<string | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [processingId, setProcessingId] = useState<string | null>(null);

  // Conversation state
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageDetail[]>([]);
  const [asking, setAsking] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [convLoading, setConvLoading] = useState(true);

  const refreshDocuments = useCallback(async () => {
    setListState("loading");
    try {
      setDocuments(await listDocuments());
      setListState("ready");
      setListError(null);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Unable to load documents.");
      setListState("error");
    }
  }, []);

  const refreshConversations = useCallback(async () => {
    try {
      setConversations(await listConversations());
    } catch {
      // non-fatal
    }
  }, []);

  useEffect(() => {
    refreshDocuments();
  }, [refreshDocuments]);

  useEffect(() => {
    (async () => {
      setConvLoading(true);
      await refreshConversations();
      setConvLoading(false);
    })();
  }, [refreshConversations]);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setUploadError(null);
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      if (title.trim()) formData.append("title", title.trim());
      await uploadDocument(formData);
      setFile(null);
      setTitle("");
      await refreshDocuments();
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.message : "Upload failed. Is the file a valid PDF?");
    } finally {
      setUploading(false);
    }
  }

  async function handleProcess(id: string) {
    setProcessingId(id);
    try {
      await processDocument(id);
      await refreshDocuments();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Processing failed.");
      await refreshDocuments();
    } finally {
      setProcessingId(null);
    }
  }

  async function handleDelete(id: string, docTitle: string) {
    if (!window.confirm(`Delete "${docTitle}"? This cannot be undone.`)) return;
    try {
      await deleteDocument(id);
      await refreshDocuments();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Delete failed.");
    }
  }

  async function selectConversation(id: string) {
    setConversationId(id);
    setMessages([]);
    setChatError(null);
    try {
      const detail = await getConversation(id);
      setMessages(detail.messages);
    } catch (err) {
      setChatError(err instanceof ApiError ? err.message : "Unable to load conversation.");
    }
  }

  async function handleNewConversation() {
    setConversationId(null);
    setMessages([]);
    setChatError(null);
  }

  async function handleDeleteConversation(id: string, convTitle: string) {
    if (!window.confirm(`Delete conversation "${convTitle}"?`)) return;
    try {
      await deleteConversation(id);
      if (conversationId === id) {
        setConversationId(null);
        setMessages([]);
      }
      await refreshConversations();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Delete failed.");
    }
  }

  async function ask(question: string) {
    setAsking(true);
    setChatError(null);
    const userMessage: MessageDetail = {
      id: `user-${Date.now()}`,
      role: "USER",
      content: question,
      created_at: new Date().toISOString(),
      citations: [],
    };
    setMessages((current) => [...current, userMessage]);
    try {
      const response = await askQuestion(question, conversationId ?? undefined);
      const assistantMessage: MessageDetail = {
        id: response.message_id,
        role: "ASSISTANT",
        content: response.answer,
        created_at: new Date().toISOString(),
        citations: response.citations,
      };
      setMessages((current) => [...current, assistantMessage]);
      if (conversationId === null || response.conversation_id !== conversationId) {
        setConversationId(response.conversation_id);
        await refreshConversations();
      }
    } catch (err) {
      setChatError(err instanceof ApiError ? err.message : "Unable to get an answer.");
      setMessages((current) => current.filter((m) => m.id !== userMessage.id));
      throw err;
    } finally {
      setAsking(false);
    }
  }

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900">
      <SiteHeader />

      <main className="mx-auto max-w-7xl px-6 py-8">
        <div className="flex flex-col gap-6 lg:flex-row">
          <aside className="lg:w-64 lg:shrink-0">
            <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500">
                  Conversations
                </h2>
                <button
                  type="button"
                  onClick={handleNewConversation}
                  className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-2 py-1 text-xs font-medium text-white hover:bg-indigo-700"
                >
                  <Plus className="h-3.5 w-3.5" aria-hidden />
                  New
                </button>
              </div>
              <div className="mt-3 space-y-1">
                {convLoading && (
                  <div className="flex items-center gap-2 py-2 text-xs text-zinc-500">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                    Loading…
                  </div>
                )}
                {!convLoading && conversations.length === 0 && (
                  <p className="py-2 text-xs text-zinc-500">
                    No conversations yet.
                  </p>
                )}
                {conversations.map((conversation) => (
                  <div
                    key={conversation.id}
                    className={cn(
                      "group flex items-center gap-1 rounded-lg border px-2 py-1.5",
                      conversation.id === conversationId
                        ? "border-indigo-200 bg-indigo-50"
                        : "border-transparent hover:border-zinc-200 hover:bg-zinc-50",
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => selectConversation(conversation.id)}
                      className="min-w-0 flex-1 truncate text-left text-sm text-zinc-700"
                      title={conversation.title}
                    >
                      {conversation.title}
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        handleDeleteConversation(conversation.id, conversation.title)
                      }
                      className="text-zinc-300 opacity-0 transition-opacity hover:text-red-600 group-hover:opacity-100"
                      aria-label={`Delete ${conversation.title}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" aria-hidden />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </aside>

          <div className="min-w-0 flex-1 space-y-8">
            <section>
              <h1 className="text-3xl font-semibold tracking-tight">
                Welcome, {user?.name}
              </h1>
              <p className="mt-1 text-zinc-600">
                {user?.role === "ADMIN"
                  ? "Administrator account"
                  : user?.role === "FACULTY"
                    ? "Faculty account"
                    : "Student account"}
              </p>
            </section>

            <ChatPanel
              conversationId={conversationId}
              messages={messages}
              setMessages={setMessages}
              asking={asking}
              ask={ask}
              chatError={chatError}
            />

            <section className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
              <div className="flex items-center gap-2">
                <Upload className="h-4 w-4 text-zinc-500" aria-hidden />
                <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500">
                  Upload a PDF
                </h2>
              </div>
              <form onSubmit={handleUpload} className="mt-4 space-y-4">
                {uploadError && <Alert variant="error">{uploadError}</Alert>}
                <div className="grid gap-4 sm:grid-cols-[1fr_auto]">
                  <div className="flex items-center gap-3">
                    <label className="flex-1 cursor-pointer rounded-lg border border-dashed border-zinc-300 px-4 py-3 text-sm text-zinc-600 transition-colors hover:border-indigo-400 hover:bg-indigo-50/40">
                      {file ? (
                        <span className="font-medium text-zinc-800">
                          {file.name} ({formatFileSize(file.size)})
                        </span>
                      ) : (
                        "Choose a PDF file…"
                      )}
                      <input
                        type="file"
                        accept=".pdf,application/pdf"
                        className="sr-only"
                        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                      />
                    </label>
                    <Input
                      className="w-48"
                      placeholder="Title (optional)"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                    />
                  </div>
                  <Button type="submit" disabled={!file || uploading} className="self-end">
                    {uploading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
                    Upload
                  </Button>
                </div>
              </form>
            </section>

            <section>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-zinc-500" aria-hidden />
                  <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500">
                    Documents
                  </h2>
                  <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-600">
                    {documents.length}
                  </span>
                </div>
                <Button variant="ghost" size="sm" onClick={refreshDocuments}>
                  <RefreshCw className="h-3.5 w-3.5" aria-hidden />
                  Refresh
                </Button>
              </div>

              {listState === "loading" && (
                <div className="mt-4 flex items-center gap-2 text-sm text-zinc-500">
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                  Loading documents…
                </div>
              )}

              {listState === "error" && (
                <Alert className="mt-4" variant="error">
                  {listError}
                </Alert>
              )}

              {listState === "ready" && documents.length === 0 && (
                <div className="mt-4 rounded-xl border border-dashed border-zinc-300 bg-white p-8 text-center text-sm text-zinc-500">
                  No documents yet. Upload a PDF above to get started.
                </div>
              )}

              {listState === "ready" && documents.length > 0 && (
                <ul className="mt-4 space-y-3">
                  {documents.map((doc) => {
                    const busy = processingId === doc.id;
                    const canProcess =
                      (doc.status === "UPLOADED" || doc.status === "FAILED") && !busy;
                    return (
                      <li
                        key={doc.id}
                        className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <h3 className="font-medium text-zinc-900">{doc.title}</h3>
                              <StatusBadge status={doc.status} />
                            </div>
                            <p className="mt-1 truncate text-sm text-zinc-500">
                              {doc.original_filename} · {formatFileSize(doc.file_size)}
                              {doc.page_count != null &&
                                ` · ${doc.page_count} page${doc.page_count === 1 ? "" : "s"}`}
                              {doc.chunk_count != null &&
                                doc.chunk_count > 0 &&
                                ` · ${doc.chunk_count} chunks`}
                            </p>
                            <p className="mt-0.5 text-xs text-zinc-400">
                              Uploaded {formatDate(doc.created_at)}
                              {doc.processed_at &&
                                ` · Processed ${formatDate(doc.processed_at)}`}
                            </p>
                          </div>
                          <div className="flex shrink-0 items-center gap-2">
                            {busy ? (
                              <span className="inline-flex items-center gap-1.5 text-xs text-amber-600">
                                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                                Processing…
                              </span>
                            ) : (
                              <>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() =>
                                    setExpandedVersions(
                                      expandedVersions === doc.id ? null : doc.id,
                                    )
                                  }
                                >
                                  <Search className="h-3.5 w-3.5" aria-hidden />
                                  Versions
                                </Button>
                                {canProcess && (
                                  <Button size="sm" onClick={() => handleProcess(doc.id)}>
                                    Process
                                  </Button>
                                )}
                                <Button
                                  size="sm"
                                  variant="destructive"
                                  onClick={() => handleDelete(doc.id, doc.title)}
                                >
                                  <Trash2 className="h-3.5 w-3.5" aria-hidden />
                                  Delete
                                </Button>
                              </>
                            )}
                          </div>
                        </div>
                        {doc.status === "FAILED" && (
                          <p className="mt-3 flex items-start gap-1.5 rounded-lg border border-red-200 bg-red-50 p-2.5 text-xs text-red-700">
                            <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                            Processing failed. You can process again after uploading a valid PDF.
                          </p>
                        )}
                        {expandedVersions === doc.id && (
                          <VersionHistory docId={doc.id} />
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardShell />
    </RequireAuth>
  );
}
