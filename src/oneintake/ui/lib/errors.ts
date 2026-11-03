import { ApiError } from "@/lib/api";

// FastAPI returns `detail` as a string (HTTPException) or a list of validation errors (422).
export function errorMessage(error: unknown, fallback = "Something went wrong. Please try again."): string {
  if (error instanceof ApiError && typeof error.body === "object" && error.body && "detail" in error.body) {
    const detail = (error.body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const parts = detail.map((item) => {
        const { loc, msg } = (item ?? {}) as { loc?: unknown[]; msg?: string };
        const field = Array.isArray(loc) ? loc.filter((p) => p !== "body").join(".") : "";
        return field ? `${field}: ${msg ?? "invalid"}` : (msg ?? "invalid");
      });
      if (parts.length) return parts.join("; ");
    }
  }
  if (error instanceof ApiError && typeof error.body === "string" && error.body.trim()) return error.body.trim();
  return error instanceof Error && error.message ? error.message : fallback;
}
