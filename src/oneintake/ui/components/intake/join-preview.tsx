import { Button } from "@/components/ui/button";
import { fieldClass } from "@/components/intake/form-field";
import { Sheet, SheetContent, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useMatchDetail, type DuplicateMatch } from "@/lib/api";
import { usd } from "@/routes/_sidebar/mine";

/** Shown before confirming "Join existing": the full detail of the candidate match, plus a
 * place to add a short description if the draft doesn't have one yet (the row needs one). */
export function JoinPreview(p: {
  match: DuplicateMatch | null;
  description: string;
  onDescriptionChange: (v: string) => void;
  pending: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const { match } = p;
  const { data, isLoading } = useMatchDetail({ params: { key: match?.key ?? "" }, query: { enabled: !!match } });
  const d = data?.data;
  const needsDescription = !p.description.trim();
  return (
    <Sheet open={!!match} onOpenChange={(open) => !open && p.onCancel()}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto" data-testid="join-preview">
        <SheetHeader><SheetTitle>{match?.title}</SheetTitle></SheetHeader>
        {isLoading && <p className="text-sm text-muted-foreground mt-2">Loading...</p>}
        {d && (
          <div className="mt-4 space-y-2 text-sm">
            <p className="text-muted-foreground">
              {d.kind === "project" ? "Tracked project" : "Existing request"} · {d.status ?? "unknown"} ·{" "}
              {d.owner ?? "no owner"}{d.business_unit && ` · ${d.business_unit}`}
            </p>
            {d.est_value_usd != null && <p>Estimated value: {usd(d.est_value_usd)}</p>}
            {d.category && <p>Category: {d.category}</p>}
            <p className="whitespace-pre-wrap">{d.description || "No description on file."}</p>
          </div>
        )}
        <div className="mt-4 space-y-1">
          <label className="text-sm font-medium">Your description {needsDescription && "*"}</label>
          <textarea className={fieldClass} value={p.description} data-testid="join-description"
            placeholder="A short note on what you were proposing, kept with your request."
            onChange={(e) => p.onDescriptionChange(e.target.value)} />
          {needsDescription && <p className="text-xs text-muted-foreground">Add a line so we keep a record of it.</p>}
        </div>
        <SheetFooter className="mt-4">
          <Button type="button" variant="outline" onClick={p.onCancel}>Cancel</Button>
          <Button type="button" disabled={needsDescription || p.pending} data-testid="confirm-join"
            onClick={p.onConfirm}>{p.pending ? "Joining..." : "Confirm join"}</Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
