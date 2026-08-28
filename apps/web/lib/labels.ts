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

/** Amazon “bought in past month” is a lower-bound badge (N+ / NK+). */
export function formatMonthlySold(value: number | null | undefined): string {
  if (value == null || value <= 0) return "Unavailable";
  if (value >= 1000 && value % 1000 === 0) {
    return `${value / 1000}K+`;
  }
  return `${value.toLocaleString("en-GB")}+`;
}

export function formatReviewsAdded(value: number | null | undefined): string {
  if (value == null) return "—";
  return `+${value.toLocaleString("en-GB")}`;
}

/** Day-over-day rating-count velocity from mobile pages — not unit sales. */
export function formatReviewMomentum(
  value: string | null | undefined,
): { text: string; className: string } {
  if (value === "rising") {
    return { text: "Rising", className: "momentum-rising" };
  }
  if (value === "steady") {
    return { text: "Steady", className: "momentum-steady" };
  }
  if (value === "quiet") {
    return { text: "Quiet", className: "momentum-quiet" };
  }
  return { text: "Building history", className: "flat" };
}
