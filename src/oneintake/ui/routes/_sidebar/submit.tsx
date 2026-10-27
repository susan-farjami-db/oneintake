import { useEffect, useRef, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FormField, fieldClass } from "@/components/intake/form-field";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  checkDuplicates, useCreateRequest, useCurrentUser, useFormConfig,
  type DuplicateMatch, type RequestOut,
} from "@/lib/api";

export const Route = createFileRoute("/_sidebar/submit")({ component: SubmitPage });

type Values = Record<string, string | string[]>;
type CheckState = "idle" | "checking" | "ok" | "failed";
const words = (s: string) => s.trim().split(/\s+/).filter(Boolean).length;
const BAND_STYLE: Record<string, string> = {
  likely_duplicate: "border-red-500 bg-red-50 dark:bg-red-950/40",
  related: "border-amber-500 bg-amber-50 dark:bg-amber-950/40",
};
const muted = "text-sm text-muted-foreground";

function SubmitPage() {
  const { data: cfg } = useFormConfig();
  const { data: me } = useCurrentUser();
  // A gateway error means the submit may not have reached the app; submission_id makes the resend safe.
  const create = useCreateRequest({ mutation: { retry: (n, e) => n < 2 && [502, 503, 504].includes(e.status) } });
  const [submissionId] = useState(() => crypto.randomUUID());
  const [values, setValues] = useState<Values>({});
  const [matches, setMatches] = useState<DuplicateMatch[]>([]);
  const [check, setCheck] = useState<CheckState>("idle");
  const [anywayReason, setAnywayReason] = useState("");
  const [needsChoice, setNeedsChoice] = useState(false);
  const [result, setResult] = useState<RequestOut | null>(null);
  const [error, setError] = useState("");
  const inflight = useRef<AbortController | null>(null);
  const form = cfg?.data;
  const dc = form?.duplicate_check;
  const title = String(values.title ?? "");
  const description = String(values.description ?? "");
  const ready = !!dc && (words(title) >= dc.min_title_words || words(description) >= dc.min_description_words);
  const visible = matches.filter((m) => m.band !== "none");
  const top = visible[0];

  async function runCheck(signal?: AbortSignal): Promise<DuplicateMatch[] | null> {
    try {
      const res = await checkDuplicates({ title, description }, undefined, { signal });
      setMatches(res.data.matches); setCheck("ok");
      return res.data.matches;
    } catch (e) {
      if ((e as Error).name === "AbortError") return null;
      if ((e as { status?: number }).status === 429) return matches;
      setCheck("failed"); return null;
    }
  }

  useEffect(() => {
    if (!ready || !dc) {
      inflight.current?.abort(); setMatches([]); setCheck("idle");
      return;
    }
    const t = setTimeout(() => {
      inflight.current?.abort();
      inflight.current = new AbortController();
      setCheck("checking");
      void runCheck(inflight.current.signal);
    }, dc.debounce_ms);
    return () => clearTimeout(t);
  }, [title, description, ready]);

  async function submit(opts: { join?: DuplicateMatch; anyway?: boolean } = {}) {
    setError("");
    inflight.current?.abort();
    let final = opts.join ? matches : await runCheck();
    const failed = final === null;
    final = (final ?? []).filter((m) => m.band !== "none");
    const best = opts.join ?? final[0];
    if (!opts.join && !opts.anyway && best?.band === "likely_duplicate") {
      setNeedsChoice(true);
      return;
    }
    const fields = { ...values, requester_email: me?.data.user_name ?? "" };
    const data = { fields, dup_score: best?.score ?? null, dup_check_failed: failed && !opts.join,
      submit_anyway_reason: opts.anyway ? anywayReason : null, join_existing: opts.join?.key ?? null,
      submission_id: submissionId };
    create.mutate({ params: {}, data }, {
      onSuccess: (r) => { setResult(r.data); setNeedsChoice(false); },
      onError: (e) => setError(JSON.stringify(e.body ?? e.message)),
    });
  }

  if (result) {
    return (
      <Card className="max-w-2xl" data-testid="submit-result">
        <CardHeader><CardTitle>{result.duplicate_of ? "Joined existing work" : "Request submitted"}</CardTitle></CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p className="font-medium">{result.title}</p>
          <p>Category: <Badge data-testid="result-category">{result.category ?? "Pending"}</Badge>
            {result.category_confidence != null && ` (${Math.round(result.category_confidence * 100)}%)`}</p>
          <p className="text-muted-foreground">Status: {result.status} {result.duplicate_of && `· linked to ${result.duplicate_of}`}</p>
          <Button variant="outline" asChild><Link to="/mine">My requests</Link></Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
      <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
        <h1 className="text-2xl font-semibold">Submit an AI request</h1>
        <p className={muted}>Tell the AI Task Force at {form?.organization_label} what you want built.</p>
        {form?.fields.map((f) => (
          <FormField key={f.field_name} f={f} me={me?.data.user_name ?? ""} value={values[f.field_name]}
            onChange={(v) => setValues((s) => ({ ...s, [f.field_name]: v }))} />
        ))}
        {needsChoice && top && (
          <Card className="border-red-500 p-4 space-y-3 text-sm" data-testid="duplicate-choice">
              <p>This looks like <b>{top.title}</b> ({top.score.toFixed(2)}). Join it, or explain why yours is different.</p>
              <textarea className={fieldClass} placeholder="Why submit anyway?" value={anywayReason}
                data-testid="anyway-reason" onChange={(e) => setAnywayReason(e.target.value)} />
              <div className="flex gap-2">
                <Button type="button" onClick={() => void submit({ join: top })}>Join existing</Button>
                <Button type="button" variant="outline" disabled={!anywayReason.trim()}
                  onClick={() => void submit({ anyway: true })}>Submit anyway</Button>
              </div>
          </Card>
        )}
        {error && <p className="text-sm text-red-600">{error}</p>}
        <Button type="submit" disabled={create.isPending} data-testid="submit-button">
          {create.isPending ? "Submitting and classifying..." : "Submit request"}
        </Button>
      </form>
      <SimilarPanel check={check} matches={visible} ready={ready} onJoin={(m) => void submit({ join: m })} />
    </div>
  );
}

function SimilarPanel(p: { check: CheckState; matches: DuplicateMatch[]; ready: boolean; onJoin: (m: DuplicateMatch) => void }) {
  return (
    <aside className="space-y-3 lg:sticky lg:top-4 self-start" data-testid="similar-panel">
      <h2 className="font-semibold">Similar projects</h2>
      {!p.ready && <p className={muted}>Checking starts after a few title words.</p>}
      {p.check === "checking" && <p className={muted}>Checking...</p>}
      {p.check === "failed" && <p className="text-sm text-amber-700" data-testid="dup-unavailable">Duplicate check unavailable</p>}
      {p.ready && p.check === "ok" && !p.matches.length && <p className={muted}>No similar work found.</p>}
      {p.matches.map((m) => (
        <div key={m.key} className={cn("rounded-md border-l-4 border p-3 text-sm space-y-1", BAND_STYLE[m.band])}
          data-testid="similar-match" data-band={m.band}>
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium">{m.title}</span>
            <span className="tabular-nums" data-testid="match-score">{m.score.toFixed(2)}</span>
          </div>
          <div className="text-xs text-muted-foreground">
            {m.band === "related" ? "Related" : "Likely duplicate"} · {m.kind} · {m.status ?? "unknown"} · {m.owner ?? "no owner"}
          </div>
          <Button size="sm" variant="outline" type="button" onClick={() => p.onJoin(m)}>Join existing</Button>
        </div>
      ))}
    </aside>
  );
}
