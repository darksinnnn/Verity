"use client";

import React, { useEffect, useState } from "react";
import { useSpring } from "framer-motion";
import { SummaryData } from "@/lib/api-client";
import { Badge } from "./ui/badge";
import { MonoText } from "./ui/mono-text";
import { ShieldCheck, AlertTriangle, HelpCircle, ArrowRight, FolderKanban } from "lucide-react";
import clsx from "clsx";

interface HeroSummaryProps {
  summary: SummaryData;
  onSelectTab?: (tab: string) => void;
}

function AnimatedNumber({ value, prefix = "", decimals = 2 }: { value: number; prefix?: string; decimals?: number }) {
  const spring = useSpring(0, { stiffness: 60, damping: 15, duration: 1.2 });
  const [display, setDisplay] = useState("0");

  useEffect(() => {
    spring.set(value);
  }, [spring, value]);

  useEffect(() => {
    return spring.on("change", (latest) => {
      setDisplay(
        latest.toLocaleString("en-IN", {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        })
      );
    });
  }, [spring, decimals]);

  return (
    <span>
      {prefix}
      {display}
    </span>
  );
}

export function HeroSummary({ summary, onSelectTab }: HeroSummaryProps) {
  const { total_expected_rs, total_received_rs, total_at_risk_rs, verdict_breakdown } = summary;

  return (
    <div className="w-full bg-bg-raised border border-divider rounded-sm p-6 lg:p-8 relative space-y-6">
      {/* Case File Docket Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-divider">
        <div className="flex items-center space-x-3">
          <FolderKanban className="w-4 h-4 text-accent-amber" />
          <span className="text-xs uppercase tracking-wider font-mono text-ink-secondary">
            SETTLEMENT CASE DOCKET <span className="text-accent-amber font-semibold">#VER-2026-09</span>
          </span>
        </div>
        <div className="flex items-center space-x-2 text-xs font-mono text-ink-muted">
          <span>CLASSIFICATION STATUS:</span>
          <Badge status="PROBABLE" label="EVIDENTIARY AUDIT ACTIVE" />
        </div>
      </div>

      {/* Main Dominant Finding Headline */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-end">
        <div className="lg:col-span-8 space-y-3">
          <p className="text-xs font-mono uppercase tracking-wider text-ink-muted">
            TOTAL AT-RISK FINANCIAL VARIANCE
          </p>
          <div className="font-display font-bold text-5xl sm:text-6xl lg:text-7xl tracking-tight text-ink-primary flex items-baseline">
            <span className="text-accent-amber mr-2 font-mono">₹</span>
            <AnimatedNumber value={total_at_risk_rs} decimals={2} />
          </div>
          <p className="text-sm text-ink-secondary max-w-2xl leading-relaxed font-sans">
            Aggregate variance across active gateway settlement runs.
            Deterministic solver confirms <MonoText variant="green">49 PROVEN</MonoText> clean matches, while{" "}
            <MonoText variant="gold">{verdict_breakdown.probable} PROBABLE</MonoText> and{" "}
            <MonoText variant="crimson">{verdict_breakdown.unresolved} UNRESOLVED</MonoText> records require documentary proof.
          </p>
        </div>

        {/* Ledger Balance Reconcile Summary Box */}
        <div className="lg:col-span-4 bg-bg-inset border border-divider p-5 rounded-sm space-y-3.5">
          <div className="flex justify-between items-center text-xs font-mono">
            <span className="text-ink-muted">TOTAL GROSS CAPTURED:</span>
            <MonoText variant="primary" className="text-sm">
              <AnimatedNumber value={total_expected_rs} prefix="₹" decimals={2} />
            </MonoText>
          </div>
          <div className="flex justify-between items-center text-xs font-mono">
            <span className="text-ink-muted">BANK CREDITS RECEIVED:</span>
            <MonoText variant="primary" className="text-sm">
              <AnimatedNumber value={total_received_rs} prefix="₹" decimals={2} />
            </MonoText>
          </div>
          <div className="pt-2 border-t border-divider flex justify-between items-center text-xs font-mono">
            <span className="text-ink-secondary font-medium">STATUTORY & FEE RETENTION:</span>
            <MonoText variant="amber" className="text-sm">
              <AnimatedNumber value={total_expected_rs - total_received_rs} prefix="₹" decimals={2} />
            </MonoText>
          </div>
        </div>
      </div>

      {/* Case-File Evidence Stubs (Replacing Generic KPI Cards) */}
      <div className="pt-4 border-t border-divider grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Stub 1: PROVEN */}
        <div
          onClick={() => onSelectTab && onSelectTab("audit")}
          className="bg-bg-inset border border-divider hover:border-status-proven/60 p-4 rounded-sm transition-all cursor-pointer group relative overflow-hidden border-l-4 border-l-status-proven"
        >
          <div className="flex justify-between items-start">
            <span className="text-[10px] font-mono uppercase tracking-widest text-status-proven font-bold">
              CASE STUB 01 • PROVEN
            </span>
            <span className="font-mono text-2xl font-bold text-ink-primary group-hover:text-status-proven transition-colors">
              {verdict_breakdown.proven}
            </span>
          </div>
          <div className="mt-2 text-xs font-mono text-ink-secondary">
            Verified Settlement Records
          </div>
          <div className="mt-2 text-[11px] text-ink-muted font-sans flex items-center justify-between">
            <span>100% UTR & Ledger backed</span>
            <ArrowRight className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 text-status-proven transition-opacity" />
          </div>
        </div>

        {/* Stub 2: PROBABLE */}
        <div
          onClick={() => onSelectTab && onSelectTab("exceptions")}
          className="bg-bg-inset border border-divider hover:border-status-probable/60 p-4 rounded-sm transition-all cursor-pointer group relative overflow-hidden border-l-4 border-l-status-probable"
        >
          <div className="flex justify-between items-start">
            <span className="text-[10px] font-mono uppercase tracking-widest text-status-probable font-bold">
              CASE STUB 02 • PROBABLE
            </span>
            <span className="font-mono text-2xl font-bold text-ink-primary group-hover:text-status-probable transition-colors">
              {verdict_breakdown.probable}
            </span>
          </div>
          <div className="mt-2 text-xs font-mono text-ink-secondary">
            Abductive Hypotheses Formulated
          </div>
          <div className="mt-2 text-[11px] text-ink-muted font-sans flex items-center justify-between">
            <span>Form 16A & settlement advice needed</span>
            <ArrowRight className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 text-status-probable transition-opacity" />
          </div>
        </div>

        {/* Stub 3: UNRESOLVED */}
        <div
          onClick={() => onSelectTab && onSelectTab("exceptions")}
          className="bg-bg-inset border border-divider hover:border-status-unresolved/60 p-4 rounded-sm transition-all cursor-pointer group relative overflow-hidden border-l-4 border-l-status-unresolved"
        >
          <div className="flex justify-between items-start">
            <span className="text-[10px] font-mono uppercase tracking-widest text-status-unresolved font-bold">
              CASE STUB 03 • UNRESOLVED
            </span>
            <span className="font-mono text-2xl font-bold text-ink-primary group-hover:text-status-unresolved transition-colors">
              {verdict_breakdown.unresolved}
            </span>
          </div>
          <div className="mt-2 text-xs font-mono text-ink-secondary">
            Unexplained Gap & Duplicate
          </div>
          <div className="mt-2 text-[11px] text-ink-muted font-sans flex items-center justify-between">
            <span>Manual investigation mandatory</span>
            <ArrowRight className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 text-status-unresolved transition-opacity" />
          </div>
        </div>
      </div>
    </div>
  );
}
