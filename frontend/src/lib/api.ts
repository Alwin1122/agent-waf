import type {
  AuditPage,
  DashboardData,
  Metrics,
  RuleActivityItem,
  RuleName,
} from "@/lib/types";

const API_PREFIX = "/backend/api/v1";

async function getJson<T>(path: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(`${API_PREFIX}${path}`, {
    cache: "no-store",
    headers: { Accept: "application/json" },
    signal,
  });

  if (!response.ok) {
    throw new Error(`API request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function fetchDashboardData(
  signal: AbortSignal,
): Promise<DashboardData> {
  const [metrics, audit] = await Promise.all([
    getJson<Metrics>("/metrics", signal),
    getJson<AuditPage>("/audit?page=1&page_size=100", signal),
  ]);
  return { metrics, audit };
}

const RULES: ReadonlyArray<{ name: RuleName; label: string }> = [
  { name: "rate_limit", label: "Rate limit" },
  { name: "parameter_validation", label: "Parameter validation" },
  { name: "data_scope", label: "Data scope" },
  { name: "sequence_enforcement", label: "Sequence enforcement" },
];

export function deriveRuleActivity(audit: AuditPage): RuleActivityItem[] {
  const results = audit.items.flatMap((event) => event.rules_evaluated);

  return RULES.map((rule) => {
    const evaluations = results.filter((result) => result.rule === rule.name);
    return {
      ...rule,
      count: evaluations.length,
      blocked: evaluations.filter((result) => result.decision === "BLOCK")
        .length,
    };
  });
}
