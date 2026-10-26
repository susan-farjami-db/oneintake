import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { FormFieldOut } from "@/lib/api";

export const fieldClass = "w-full rounded-md border bg-transparent px-3 py-2 text-sm";

/** Renders one config-driven intake form field (text, textarea, select, multiselect, number, email). */
export function FormField({ f, value, onChange, me }: { f: FormFieldOut; value?: string | string[]; me: string; onChange: (v: string | string[]) => void }) {
  const id = `field-${f.field_name}`;
  const common = { id, required: f.required, value: String(value ?? ""),
    onChange: (e: { target: { value: string } }) => onChange(e.target.value) };
  let input;
  if (f.type === "textarea") {
    input = <textarea {...common} className={cn(fieldClass, "min-h-24")} />;
  } else if (f.type === "select") {
    input = (
      <select {...common} className={fieldClass}>
        <option value="">Select...</option>
        {f.options?.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    );
  } else if (f.type === "multiselect") {
    const sel = Array.isArray(value) ? value : [];
    input = (
      <div id={id} className="flex flex-wrap gap-2">
        {f.options?.map((o) => (
          <label key={o} className="flex items-center gap-1 text-sm">
            <input type="checkbox" checked={sel.includes(o)}
              onChange={(e) => onChange(e.target.checked ? [...sel, o] : sel.filter((x) => x !== o))} />{o}
          </label>
        ))}
      </div>
    );
  } else if (f.type === "email") {
    input = <Input id={id} type="email" value={me} readOnly />;
  } else {
    input = <Input {...common} type={f.type === "number" ? "number" : "text"} min={f.type === "number" ? 0 : undefined} />;
  }
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="text-sm font-medium">{f.label}{f.required && " *"}</label>{input}
    </div>
  );
}
