import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useReviewQueue, useReviewRequest, type ReviewItemOut } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { usd } from "./mine";

export const Route = createFileRoute("/_sidebar/review")({ component: ReviewQueue });

function ReviewQueue() {
  const { data, isLoading, error } = useReviewQueue();
  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (error) {
    const forbidden = (error as { status?: number }).status === 403;
    return <p className="text-red-600">{forbidden ? "The review queue is for Task Force members." : "Could not load the queue."}</p>;
  }
  const rows = data?.data ?? [];
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Review queue</h1>
      <p className="text-sm text-muted-foreground">{rows.length} open requests, newest first.</p>
      {rows.map((r) => <ReviewCard key={r.request_id} r={r} />)}
    </div>
  );
}

function ReviewCard({ r }: { r: ReviewItemOut }) {
  const review = useReviewRequest();
  const [target, setTarget] = useState(r.top_match?.key ?? r.duplicate_of ?? "");
  const [reason, setReason] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState("");
  const m = r.top_match;
  const act = (action: "approve" | "merge" | "reject") => {
    setError("");
    review.mutate(
      { params: { request_id: r.request_id }, data: { action, merged_into: action === "merge" ? target : null, reason: reason || null } },
      {
        onSuccess: (res) => setDone(res.data.status),
        onError: (e) => setError(errorMessage(e, `Could not ${action} this request. Please try again.`)),
      },
    );
  };
  return (
    <Card data-testid="review-item" data-title={r.title}>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center justify-between gap-2 text-base">
          <span>{r.title}</span>
          <span className="flex gap-1">
            <Badge variant="secondary">{r.category ?? "uncategorized"}</Badge>
            <Badge variant="outline">{r.status}</Badge>
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="text-muted-foreground">{r.description}</p>
        <div className="flex flex-wrap gap-x-6 text-muted-foreground">
          <span>{r.business_unit}</span><span>{usd(r.est_value_usd)}</span><span>{r.requester_email}</span>
          {r.submit_anyway_reason && <span>Submitted anyway: {r.submit_anyway_reason}</span>}
          {r.dup_check_failed && <span className="text-amber-700">Duplicate check was unavailable</span>}
        </div>
        {m && m.band !== "none" && (
          <div className={`rounded-md border-l-4 border p-2 ${m.band === "likely_duplicate" ? "border-red-500" : "border-amber-500"}`}>
            Closest match: <b>{m.title}</b> ({m.score.toFixed(2)}, {m.kind}, {m.status ?? "unknown"}, {m.owner ?? "no owner"})
          </div>
        )}
        {done ? (
          <p className="font-medium" data-testid="review-done">Marked {done}.</p>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" onClick={() => act("approve")} disabled={review.isPending}>Approve</Button>
            <Input className="w-48" placeholder="Merge into id" value={target} onChange={(e) => setTarget(e.target.value)} />
            <Button size="sm" variant="secondary" onClick={() => act("merge")} disabled={!target || review.isPending}>Merge</Button>
            <Input className="w-56" placeholder="Note (optional)" value={reason} onChange={(e) => setReason(e.target.value)} />
            <Button size="sm" variant="destructive" onClick={() => act("reject")} disabled={review.isPending}>Reject</Button>
          </div>
        )}
        {error && <p className="text-sm text-red-600" role="alert">{error}</p>}
      </CardContent>
    </Card>
  );
}
