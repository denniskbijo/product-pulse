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
