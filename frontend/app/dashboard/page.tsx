"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  BookOpen,
  FileText,
  Loader2,
  MessageSquareText,
  RefreshCw,
  Send,
  Trash2,
  TriangleAlert,
  Upload,
} from "lucide-react";

import { RequireAuth } from "@/components/require-auth";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { type Citation, askQuestion } from "@/lib/chat";
import {
  type CampusDocument,
  type DocumentStatus,
  deleteDocument,
  formatDate,
  formatFileSize,
  listDocuments,
  processDocument,
  uploadDocument,
} from "@/lib/documents";
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

function CitationList({
  citations,
}: {
  citations: Citation[];
}) {
  if (citations.length === 0) return null;
  return (
    <div className="mt-4 border-t border-zinc-100 pt-3">
      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-400">
        Sources ({citations.length})
      </p>
      <ul className="space-y-1.5">
        {citations.map((citation) => {
          const label =
            citation.section ??
            (citation.page_number != null ? `p. ${citation.page_number}` : null);
          const relevance =
            citation.relevance_score != null
              ? `Relevance: ${citation.relevance_score.toFixed(2)}`
              : null;
          return (
            <li
              key={citation.chunk_id + citation.chunk_index}
              className="text-xs text-zinc-600"
            >
              <span className="font-medium text-zinc-800">
                {citation.document_title}
              </span>
              {label && <span className="text-zinc-400"> · {label}</span>}
              {relevance && <span className="text-indigo-600"> · {relevance}</span>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function ChatPanel() {
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState<string | null>(null);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [chatError, setChatError] = useState<string | null>(null);

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || asking) return;
    setAsking(true);
    setChatError(null);
    setAnswer(null);
    setCitations([]);
    try {
      const response = await askQuestion(trimmed);
      setAnswer(response.answer);
      setCitations(response.citations);
    } catch (err) {
      setChatError(
        err instanceof ApiError ? err.message : "Unable to get an answer.",
      );
    } finally {
      setAsking(false);
    }
  }

  return (
    <section className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
      <div className="flex items-center gap-2">
        <MessageSquareText className="h-4 w-4 text-zinc-500" aria-hidden />
        <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500">
          Ask an academic question
        </h2>
      </div>
      <p className="mt-1 text-sm text-zinc-500">
        Answers are grounded in the documents you can view.
      </p>

      <form onSubmit={handleAsk} className="mt-4 flex items-center gap-3">
        <Input
          className="flex-1"
          placeholder="e.g. What is the attendance policy?"
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

      {chatError && <Alert className="mt-4" variant="error">{chatError}</Alert>}

      {answer && (
        <div className="mt-4 rounded-lg border border-zinc-100 bg-zinc-50 p-4">
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-800">
            {answer.replace(/\s*Sources:\s*\[[\d,\s]+\]\s*$/, "").trim()}
          </p>
          <CitationList citations={citations} />
        </div>
      )}
    </section>
  );
}

function DashboardShell() {
  const { user, logout } = useAuth();
  const router = useRouter();

  const [documents, setDocuments] = useState<CampusDocument[]>([]);
  const [listState, setListState] = useState<
    "loading" | "ready" | "error"
  >("loading");
  const [listError, setListError] = useState<string | null>(null);

  // Upload state
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Processing state: which document is currently being processed
  const [processingId, setProcessingId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setListState("loading");
    try {
      setDocuments(await listDocuments());
      setListState("ready");
      setListError(null);
    } catch (err) {
      setListError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Unable to load documents.",
      );
      setListState("error");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  function handleLogout() {
    logout();
    router.push("/");
  }

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
      await refresh();
    } catch (err) {
      setUploadError(
        err instanceof ApiError
          ? err.message
          : "Upload failed. Is the file a valid PDF?",
      );
    } finally {
      setUploading(false);
    }
  }

  async function handleProcess(id: string) {
    setProcessingId(id);
    try {
      await processDocument(id);
      await refresh();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Processing failed.");
      await refresh();
    } finally {
      setProcessingId(null);
    }
  }

  async function handleDelete(id: string, title: string) {
    if (!window.confirm(`Delete "${title}"? This cannot be undone.`)) return;
    try {
      await deleteDocument(id);
      await refresh();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Delete failed.");
    }
  }

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900">
      <header className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2 font-semibold">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white">
              <BookOpen className="h-4 w-4" aria-hidden />
            </span>
            CampusRAG
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-zinc-600 sm:inline">
              {user?.email}
            </span>
            <Button variant="outline" size="sm" onClick={handleLogout}>
              Logout
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-4xl space-y-8 px-6 py-10">
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
              <Button
                type="submit"
                disabled={!file || uploading}
                className="self-end"
              >
                {uploading && (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                )}
                Upload
              </Button>
            </div>
          </form>
        </section>

        <ChatPanel />

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
            <Button variant="ghost" size="sm" onClick={refresh}>
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
                          <h3 className="font-medium text-zinc-900">
                            {doc.title}
                          </h3>
                          <StatusBadge status={doc.status} />
                        </div>
                        <p className="mt-1 truncate text-sm text-zinc-500">
                          {doc.original_filename} · {formatFileSize(doc.file_size)}
                          {doc.page_count != null && ` · ${doc.page_count} page${doc.page_count === 1 ? "" : "s"}`}
                          {doc.chunk_count != null && doc.chunk_count > 0 && ` · ${doc.chunk_count} chunks`}
                        </p>
                        <p className="mt-0.5 text-xs text-zinc-400">
                          Uploaded {formatDate(doc.created_at)}
                          {doc.processed_at && ` · Processed ${formatDate(doc.processed_at)}`}
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
                        Processing failed. You can process again after uploading
                        a valid PDF.
                      </p>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </section>
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