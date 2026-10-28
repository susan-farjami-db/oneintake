import { FormEvent, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useCurrentUser } from "@/lib/api";

type AskOut = {
  conversation_id: string;
  answer: string;
  sql: string | null;
  columns: string[];
  rows: string[][];
};
type Turn = { role: "user" | "assistant"; text: string; sql?: string | null; columns?: string[]; rows?: string[][] };

const QUESTIONS = [
  "What is the backlog value by business unit?",
  "How many requests have been waiting more than 30 days?",
  "What is the duplicate rate by month?",
  "What are the top 5 requests by estimated value that are still in review?",
];

async function postAsk(question: string, conversation_id: string | null): Promise<AskOut> {
  const res = await fetch("/api/genie/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, conversation_id }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body.slice(0, 400) || res.statusText);
  }
  return res.json();
}

export function GenieChat({ configured }: { configured: boolean }) {
  const { data: me } = useCurrentUser();
  const email = me?.data.user_name ?? "Signed in";
  const [q, setQ] = useState("");
  const [cid, setCid] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [status, setStatus] = useState<"idle" | "streaming" | "error">("idle");
  const [error, setError] = useState("");

  async function ask(question: string) {
    const text = question.trim();
    if (!text || status === "streaming") return;
    setTurns((t) => [...t, { role: "user", text }]);
    setQ("");
    setStatus("streaming");
    setError("");
    try {
      const out = await postAsk(text, cid);
      setCid(out.conversation_id);
      setTurns((t) => [...t, {
        role: "assistant", text: out.answer, sql: out.sql,
        columns: out.columns, rows: out.rows,
      }]);
      setStatus("idle");
    } catch (e) {
      setStatus("error");
      setError(e instanceof Error ? e.message : "Genie failed — rephrase or retry.");
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void ask(q);
  }

  if (!configured) {
    return (
      <Card data-testid="genie-chat">
        <CardHeader><CardTitle>Ask the portfolio</CardTitle></CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Genie is not configured for this deployment. Set <code>GENIE_SPACE_ID</code> and redeploy.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card data-testid="genie-chat" className="flex min-h-[28rem] flex-col">
      <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0">
        <CardTitle>Ask the portfolio</CardTitle>
        <Badge variant="secondary">{email}</Badge>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-3">
        <p className="text-xs text-muted-foreground">
          Runs as you (on-behalf-of-user). Row filters apply. AI-generated — review the SQL before trusting results.
        </p>
        <div className="flex flex-wrap gap-2">
          {QUESTIONS.map((s) => (
            <Button key={s} type="button" variant="outline" size="sm" className="h-auto whitespace-normal text-left"
                    onClick={() => void ask(s)} disabled={status === "streaming"}>{s}</Button>
          ))}
        </div>
        <div className="min-h-[12rem] flex-1 space-y-3 overflow-auto rounded-md border p-3 text-sm">
          {turns.length === 0 && status === "idle" && (
            <p className="text-muted-foreground">Ask a question, or pick one of the samples above.</p>
          )}
          {turns.map((t, i) => (
            <div key={i} className={t.role === "user" ? "ml-8" : "mr-8"}>
              <p className="text-xs font-medium text-muted-foreground">{t.role === "user" ? "You" : "Genie"}</p>
              <p className="whitespace-pre-wrap">{t.text.replace(/\*\*/g, "")}</p>
              {t.role === "assistant" && t.sql && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-xs text-muted-foreground">Generated SQL</summary>
                  <pre className="mt-1 overflow-auto rounded bg-muted p-2 text-xs">{t.sql}</pre>
                </details>
              )}
              {t.role === "assistant" && t.rows && t.rows.length > 0 && (
                <div className="mt-2 overflow-auto">
                  <table className="w-full text-xs">
                    <thead><tr>{t.columns?.map((c) => <th key={c} className="border-b px-2 py-1 text-left">{c}</th>)}</tr></thead>
                    <tbody>
                      {t.rows.map((r, ri) => (
                        <tr key={ri}>{r.map((c, ci) => <td key={ci} className="border-b px-2 py-1 tabular-nums">{c}</td>)}</tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {t.role === "assistant" && (
                <p className="mt-1 text-[11px] text-muted-foreground">AI-generated — verify against the SQL.</p>
              )}
            </div>
          ))}
          {status === "streaming" && <p className="text-muted-foreground">Analyzing your data…</p>}
          {status === "error" && <p className="text-red-600" role="alert">{error}</p>}
        </div>
        <form className="flex gap-2" onSubmit={onSubmit}>
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about backlog, duplicates, or value…"
                 disabled={status === "streaming"} aria-label="Genie question" />
          <Button type="submit" disabled={status === "streaming" || !q.trim()}>Ask</Button>
        </form>
      </CardContent>
    </Card>
  );
}
