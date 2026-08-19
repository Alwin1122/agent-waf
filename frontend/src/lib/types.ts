export type AuditDecision = "ALLOW" | "BLOCK" | "WOULD_BLOCK";
export type EnforcementMode = "ENFORCE" | "SHADOW";

export interface RuleResult {
  rule: string;
  decision: "ALLOW" | "BLOCK";
  reason: string;
}

export interface AuditEvent {
  timestamp: string;
  request_id: string | null;
  agent_id: string;
  session_id: string;
  tool: string;
  sanitized_parameters: Record<string, unknown>;
  rules_evaluated: RuleResult[];
  decision: AuditDecision;
  reason: string;
  enforcement_mode: EnforcementMode;
  latency_ms: number;
}

export interface AuditPage {
  items: AuditEvent[];
  page: number;
  page_size: number;
  total: number;
}

export interface Metrics {
  total_requests: number;
  allowed: number;
  blocked: number;
  would_block: number;
}

export interface DashboardData {
  metrics: Metrics;
  audit: AuditPage;
}

export type RuleName =
  | "rate_limit"
  | "parameter_validation"
  | "data_scope"
  | "sequence_enforcement";

export interface RuleActivityItem {
  name: RuleName;
  label: string;
  count: number;
  blocked: number;
}
