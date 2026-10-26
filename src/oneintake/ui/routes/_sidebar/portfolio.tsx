import { createFileRoute } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { usePortfolioSummary } from "@/lib/api";
import { usd } from "./mine";

export const Route = createFileRoute("/_sidebar/portfolio")({ component: Portfolio });

function Kpi({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <Card data-testid="kpi">
      <CardHeader className="pb-1"><CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle></CardHeader>
      <CardContent>
        <div className="text-3xl font-semibold tabular-nums">{value}</div>
        <p className="text-xs text-muted-foreground">{hint}</p>
      </CardContent>
    </Card>
  );
}

function Portfolio() {
  const { data, isLoading, error } = usePortfolioSummary();
  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (error || !data) return <p className="text-red-600">Could not load portfolio metrics.</p>;
  const p = data.data;
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold">AI portfolio</h1>
        {p.genie_url && (
          <Button asChild><a href={p.genie_url} target="_blank" rel="noreferrer">Ask Genie about the portfolio</a></Button>
        )}
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <Kpi label="Requests" value={p.request_count.toLocaleString()} hint={`${usd(p.total_est_value)} estimated annual value`} />
        <Kpi label="Open backlog value" value={usd(p.open_backlog_value)} hint="Submitted or in review" />
        <Kpi label="Duplicate rate" value={`${(p.duplicate_rate * 100).toFixed(1)}%`} hint="Requests that repeat existing work" />
      </div>
      <p className="text-sm text-muted-foreground">Figures come from the governed metric view and respect your business-unit access.</p>
    </div>
  );
}
