import { createFileRoute } from "@tanstack/react-router";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyRequests } from "@/lib/api";

export const Route = createFileRoute("/_sidebar/mine")({ component: MyRequests });

export const usd = (v?: number | null) =>
  v == null ? "-" : v.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

function MyRequests() {
  const { data, isLoading, error } = useMyRequests();
  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (error) return <p className="text-red-600">Could not load your requests.</p>;
  const rows = data?.data ?? [];
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">My requests</h1>
      {rows.length === 0 && <p className="text-muted-foreground">You have not submitted any requests yet.</p>}
      {rows.map((r) => (
        <Card key={r.request_id} data-testid="my-request">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center justify-between gap-2 text-base">
              <span>{r.title}</span>
              <Badge variant={r.status === "rejected" ? "destructive" : "secondary"}>{r.status}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
            <span>Category: {r.category ?? "pending"}</span>
            <span>Business unit: {r.business_unit ?? "-"}</span>
            <span>Value: {usd(r.est_value_usd)}</span>
            <span>Submitted: {r.submitted_at ? new Date(r.submitted_at).toLocaleDateString() : "-"}</span>
            {r.duplicate_of && <span>Linked to {r.duplicate_of}</span>}
            {r.dup_check_failed && <span className="text-amber-700">Duplicate check was unavailable</span>}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
