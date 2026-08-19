"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { deriveRuleActivity, fetchDashboardData } from "@/lib/api";
import type {
  AuditDecision,
  AuditEvent,
  DashboardData,
  Metrics,
  RuleActivityItem,
} from "@/lib/types";

const POLL_INTERVAL_MS = 2_000;

const numberFormatter = new Intl.NumberFormat("en-US");
const timeFormatter = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

const summaryConfig: ReadonlyArray<{
  key: keyof Metrics;
  label: string;
  tone: "blue" | "green" | "red" | "amber";
  icon: "activity" | "check" | "block" | "eye";
}> = [
  {
    key: "total_requests",
    label: "Total requests",
    tone: "blue",
    icon: "activity",
  },
  { key: "allowed", label: "Allowed", tone: "green", icon: "check" },
  { key: "blocked", label: "Blocked", tone: "red", icon: "block" },
  {
    key: "would_block",
    label: "Would block",
    tone: "amber",
    icon: "eye",
  },
];

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const activeRequest = useRef<AbortController | null>(null);
  const hasData = useRef(false);

  const load = useCallback(async () => {
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    if (hasData.current) setRefreshing(true);

    try {
      const nextData = await fetchDashboardData(controller.signal);
      setData(nextData);
      hasData.current = true;
      setError(null);
      setLastUpdated(new Date());
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === "AbortError") return;
      setError(
        cause instanceof Error
          ? cause.message
          : "The dashboard API is unavailable.",
      );
    } finally {
      if (activeRequest.current === controller) setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const interval = window.setInterval(() => void load(), POLL_INTERVAL_MS);
    return () => {
      window.clearInterval(interval);
      activeRequest.current?.abort();
    };
  }, [load]);

  if (!data && !error) return <DashboardSkeleton />;
  if (!data) return <FullPageError message={error ?? "Unknown API error"} retry={load} />;

  const ruleActivity = deriveRuleActivity(data.audit);

  return (
    <div className="min-h-screen bg-[#f4f7fb] text-slate-950">
      <Header
        refreshing={refreshing}
        lastUpdated={lastUpdated}
        onRefresh={load}
      />

      <main className="mx-auto max-w-[1480px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <div className="mb-7 flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-blue-700">
              Security operations
            </p>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-950 sm:text-3xl">
              Agent activity overview
            </h1>
            <p className="mt-1.5 text-sm text-slate-500">
              Live policy decisions and protected tool activity.
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs font-medium text-slate-500">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-40" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            Auto-refreshing every 2 seconds
          </div>
        </div>

        {error ? <ErrorBanner message={error} /> : null}

        <section
          aria-label="Request summary"
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"
        >
          {summaryConfig.map((item) => (
            <SummaryCard
              key={item.key}
              label={item.label}
              value={data.metrics[item.key]}
              tone={item.tone}
              icon={item.icon}
            />
          ))}
        </section>

        <section className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
          <RecentCalls events={data.audit.items.slice(0, 12)} />
          <RuleActivity
            items={ruleActivity}
            sampleSize={data.audit.items.length}
          />
        </section>
      </main>
    </div>
  );
}

function Header({
  refreshing,
  lastUpdated,
  onRefresh,
}: {
  refreshing: boolean;
  lastUpdated: Date | null;
  onRefresh: () => void;
}) {
  return (
    <header className="sticky top-0 z-20 border-b border-slate-200/90 bg-white/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-[1480px] items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-slate-950 text-white shadow-sm">
            <ShieldIcon />
          </div>
          <div>
            <p className="text-sm font-semibold tracking-tight text-slate-950">
              Agent WAF
            </p>
            <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-slate-400">
              Control plane
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden text-right sm:block">
            <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
              Last updated
            </p>
            <p className="text-xs font-medium tabular-nums text-slate-600">
              {lastUpdated ? timeFormatter.format(lastUpdated) : "Waiting…"}
            </p>
          </div>
          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing}
            className="grid h-9 w-9 place-items-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            aria-label="Refresh dashboard"
          >
            <RefreshIcon spinning={refreshing} />
          </button>
        </div>
      </div>
    </header>
  );
}

function SummaryCard({
  label,
  value,
  tone,
  icon,
}: {
  label: string;
  value: number;
  tone: "blue" | "green" | "red" | "amber";
  icon: "activity" | "check" | "block" | "eye";
}) {
  const styles = {
    blue: "bg-blue-50 text-blue-700 ring-blue-100",
    green: "bg-emerald-50 text-emerald-700 ring-emerald-100",
    red: "bg-rose-50 text-rose-700 ring-rose-100",
    amber: "bg-amber-50 text-amber-700 ring-amber-100",
  }[tone];

  return (
    <article className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.03)]">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-slate-500">{label}</p>
          <p className="mt-2 text-3xl font-semibold tracking-tight tabular-nums text-slate-950">
            {numberFormatter.format(value)}
          </p>
        </div>
        <div className={`grid h-10 w-10 place-items-center rounded-lg ring-1 ${styles}`}>
          <SummaryIcon name={icon} />
        </div>
      </div>
    </article>
  );
}

function RecentCalls({ events }: { events: AuditEvent[] }) {
  return (
    <section className="overflow-hidden rounded-xl border border-slate-200/80 bg-white shadow-[0_1px_2px_rgba(15,23,42,0.03)]">
      <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-950">
            Recent tool calls
          </h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Most recent WAF-intercepted requests
          </p>
        </div>
        <span className="rounded-md bg-slate-100 px-2 py-1 text-[11px] font-semibold text-slate-600">
          LIVE
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[860px] text-left">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50/60 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-400">
              <th className="px-5 py-3">Timestamp</th>
              <th className="px-4 py-3">Agent</th>
              <th className="px-4 py-3">Tool</th>
              <th className="px-4 py-3">Decision</th>
              <th className="px-4 py-3">Rule / reason</th>
              <th className="px-5 py-3 text-right">Latency</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {events.map((event) => (
              <AuditRow key={event.request_id ?? `${event.timestamp}-${event.tool}`} event={event} />
            ))}
          </tbody>
        </table>
        {events.length === 0 ? (
          <div className="grid min-h-56 place-items-center px-6 text-center">
            <div>
              <div className="mx-auto mb-3 grid h-10 w-10 place-items-center rounded-full bg-slate-100 text-slate-400">
                <ActivityIcon />
              </div>
              <p className="text-sm font-medium text-slate-700">
                No tool calls recorded
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Events will appear here as the WAF processes requests.
              </p>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function AuditRow({ event }: { event: AuditEvent }) {
  const blockingRule = event.rules_evaluated.find(
    (result) => result.decision === "BLOCK",
  )?.rule;
  const rule = blockingRule ?? event.rules_evaluated.at(-1)?.rule;

  return (
    <tr className="text-sm transition-colors hover:bg-slate-50/70">
      <td className="whitespace-nowrap px-5 py-3.5 text-xs tabular-nums text-slate-500">
        {formatTimestamp(event.timestamp)}
      </td>
      <td className="px-4 py-3.5">
        <p className="font-medium text-slate-800">{event.agent_id}</p>
        <p className="mt-0.5 max-w-40 truncate text-[11px] text-slate-400">
          {event.session_id}
        </p>
      </td>
      <td className="px-4 py-3.5">
        <code className="rounded bg-slate-100 px-1.5 py-1 text-xs font-medium text-slate-700">
          {event.tool}
        </code>
      </td>
      <td className="px-4 py-3.5">
        <DecisionBadge decision={event.decision} />
      </td>
      <td className="max-w-[320px] px-4 py-3.5">
        <p className="truncate text-xs font-medium text-slate-700">
          {formatRuleName(rule)}
        </p>
        <p className="mt-0.5 truncate text-xs text-slate-400" title={event.reason}>
          {event.reason}
        </p>
      </td>
      <td className="whitespace-nowrap px-5 py-3.5 text-right text-xs tabular-nums text-slate-500">
        {event.latency_ms.toFixed(1)} ms
      </td>
    </tr>
  );
}

function DecisionBadge({ decision }: { decision: AuditDecision }) {
  const style = {
    ALLOW: "bg-emerald-50 text-emerald-700 ring-emerald-600/15",
    BLOCK: "bg-rose-50 text-rose-700 ring-rose-600/15",
    WOULD_BLOCK: "bg-amber-50 text-amber-700 ring-amber-600/20",
  }[decision];

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[10px] font-bold tracking-wide ring-1 ring-inset ${style}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          decision === "ALLOW"
            ? "bg-emerald-500"
            : decision === "BLOCK"
              ? "bg-rose-500"
              : "bg-amber-500"
        }`}
      />
      {decision.replace("_", " ")}
    </span>
  );
}

function RuleActivity({
  items,
  sampleSize,
}: {
  items: RuleActivityItem[];
  sampleSize: number;
}) {
  const maximum = Math.max(...items.map((item) => item.count), 1);

  return (
    <section className="rounded-xl border border-slate-200/80 bg-white shadow-[0_1px_2px_rgba(15,23,42,0.03)]">
      <div className="border-b border-slate-100 px-5 py-4">
        <h2 className="text-sm font-semibold text-slate-950">Rule activity</h2>
        <p className="mt-0.5 text-xs text-slate-500">
          Evaluations across the latest {sampleSize} events
        </p>
      </div>
      <div className="space-y-6 p-5">
        {items.map((item) => (
          <div key={item.name}>
            <div className="mb-2 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-slate-700">{item.label}</p>
                <p className="mt-0.5 text-[11px] text-slate-400">
                  {item.blocked} violation{item.blocked === 1 ? "" : "s"}
                </p>
              </div>
              <span className="text-sm font-semibold tabular-nums text-slate-800">
                {numberFormatter.format(item.count)}
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
              <div
                className={`h-full rounded-full ${
                  item.blocked > 0 ? "bg-amber-500" : "bg-blue-600"
                }`}
                style={{ width: `${(item.count / maximum) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
      <div className="mx-5 mb-5 rounded-lg border border-blue-100 bg-blue-50/70 p-3">
        <div className="flex gap-2.5">
          <div className="mt-0.5 text-blue-600">
            <ShieldIcon />
          </div>
          <p className="text-xs leading-5 text-blue-800">
            Counts represent rule evaluations in the current audit window. The
            backend remains the source of truth.
          </p>
        </div>
      </div>
    </section>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="mb-5 flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
    >
      <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-amber-100 font-bold">
        !
      </span>
      <div>
        <span className="font-semibold">Refresh failed.</span>{" "}
        <span className="text-amber-800">{message}</span>
        <span className="ml-1 text-amber-700">Showing the last successful data.</span>
      </div>
    </div>
  );
}

function FullPageError({
  message,
  retry,
}: {
  message: string;
  retry: () => void;
}) {
  return (
    <div className="grid min-h-screen place-items-center bg-[#f4f7fb] px-6">
      <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-7 text-center shadow-sm">
        <div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-full bg-rose-50 text-xl font-bold text-rose-600">
          !
        </div>
        <h1 className="text-lg font-semibold text-slate-950">
          Dashboard API unavailable
        </h1>
        <p className="mt-2 text-sm leading-6 text-slate-500">{message}</p>
        <button
          type="button"
          onClick={retry}
          className="mt-5 rounded-lg bg-slate-950 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800"
        >
          Try again
        </button>
      </div>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="min-h-screen bg-[#f4f7fb]">
      <div className="h-16 border-b border-slate-200 bg-white" />
      <div className="mx-auto max-w-[1480px] px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-7 h-16 w-80 animate-pulse rounded-lg bg-slate-200/70" />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <div
              key={index}
              className="h-32 animate-pulse rounded-xl border border-slate-200 bg-white"
            />
          ))}
        </div>
        <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="h-[520px] animate-pulse rounded-xl border border-slate-200 bg-white" />
          <div className="h-[520px] animate-pulse rounded-xl border border-slate-200 bg-white" />
        </div>
      </div>
    </div>
  );
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Invalid date" : timeFormatter.format(date);
}

function formatRuleName(rule?: string): string {
  if (!rule) return "Policy evaluation";
  return rule
    .split("_")
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(" ");
}

function ShieldIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none">
      <path
        d="M12 3 5.5 5.8v5.6c0 4.2 2.6 7.9 6.5 9.6 3.9-1.7 6.5-5.4 6.5-9.6V5.8L12 3Z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path d="m9 12 2 2 4-4" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
}

function RefreshIcon({ spinning }: { spinning: boolean }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className={`h-4 w-4 ${spinning ? "animate-spin" : ""}`}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <path d="M20 11a8 8 0 1 0-2.3 5.7" />
      <path d="M20 5v6h-6" />
    </svg>
  );
}

function SummaryIcon({ name }: { name: "activity" | "check" | "block" | "eye" }) {
  if (name === "check") {
    return (
      <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="m5 12 4 4L19 6" />
      </svg>
    );
  }
  if (name === "block") {
    return (
      <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
        <circle cx="12" cy="12" r="8" />
        <path d="m7 7 10 10" />
      </svg>
    );
  }
  if (name === "eye") {
    return (
      <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M3 12s3.3-6 9-6 9 6 9 6-3.3 6-9 6-9-6-9-6Z" />
        <circle cx="12" cy="12" r="2.5" />
      </svg>
    );
  }
  return <ActivityIcon />;
}

function ActivityIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M4 13h4l2-6 4 10 2-4h4" />
    </svg>
  );
}
