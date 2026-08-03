/** Stakeholder-facing labels for internal API enum values. */

export function formatEstimateSource(source: string | null | undefined): string | null {
  if (!source || source === "unavailable") return null;
  if (source === "monthly_sold") {
    return "Based on Amazon “bought in past month”";
  }
  if (source === "bsr_curve") {
    return "Estimated from Best Sellers Rank";
  }
  return null;
}

export function formatPriceHistorySource(source: string): string {
  if (source === "amazon_mobile") return "Daily check";
  if (source === "weekly_snapshot") return "Weekly update";
  return source;
}

export function formatPriceChange(
  absolute: number | null,
  percent: number | null,
): { text: string; className: string } {
  if (absolute == null) {
    return { text: "No history yet", className: "flat" };
  }
  const sign = absolute > 0 ? "+" : "";
  const pct = percent == null ? "" : ` (${sign}${percent.toFixed(1)}%)`;
  const className = absolute > 0 ? "up" : absolute < 0 ? "down" : "flat";
  return {
    text: `${sign}${absolute.toFixed(2)}${pct}`,
    className,
  };
}

export function formatBsr(bsr: number | null | undefined): string {
  if (bsr == null) return "Unavailable";
  return bsr.toLocaleString("en-GB");
}
