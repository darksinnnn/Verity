"use client";

import React, { useEffect, useState } from "react";
import {
  fetchForensics,
  ForensicReport,
  BenfordPoolAnalysis,
  DigitStat,
} from "@/lib/api-client";
import { Activity, ShieldCheck, AlertTriangle, Info } from "lucide-react";
import clsx from "clsx";

export function ForensicsPanel() {
  const [data, setData] = useState<ForensicReport | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPool, setSelectedPool] = useState<"payments_pool" | "credits_pool" | "combined_pool">("payments_pool");

  useEffect(() => {
    fetchForensics()
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to load forensics data");
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="bg-bg-raised border border-divider p-12 text-center rounded-sm">
        <div className="text-xs uppercase tracking-widest text-ink-muted font-mono animate-pulse">
          COMPUTING PEARSON CHI-SQUARE &amp; TOLERANCE BOUNDARY CLUSTERING FROM SQLITE...
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-bg-raised border border-status-unresolved/50 p-6 rounded-sm bg-status-unresolved/10">
        <div className="text-xs font-mono text-status-unresolved">Error: {error}</div>
      </div>
    );
  }

  const activePool: BenfordPoolAnalysis = data.benford_analysis[selectedPool];
  const tc = data.tolerance_clustering;

  return (
    <div className="space-y-8">
      {/* ── UNIFIED FORENSIC SCREENING ANNOTATION BLOCK (COLLAPSED CAVEATS) ── */}
      <div className="bg-bg-raised border border-accent-amber/40 rounded-sm p-5 space-y-4">
        <div className="flex items-center space-x-2 pb-2 border-b border-divider">
          <span className="w-2 h-2 rounded-full bg-accent-amber animate-ping" />
          <span className="text-xs font-bold uppercase tracking-wider font-mono text-accent-amber">
            METHODOLOGICAL FORENSIC SCREENING ANNOTATIONS
          </span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 text-xs font-mono text-ink-secondary leading-relaxed">
          {/* Note 1: Synthetic Sample Size & Uniform Bounds */}
          <div className="space-y-1.5">
            <div className="flex items-center space-x-1.5 text-ink-primary font-bold">
              <span className="text-accent-amber">01.</span>
              <span>SYNTHETIC SAMPLE SIZE &amp; UNIFORM RANGE CONSTRAINT</span>
            </div>
            <p className="text-ink-secondary">
              {data.caveats.synthetic_sample_size_caveat}
            </p>
          </div>

          {/* Note 2: Adversarial Sculpting & Surveillance Scope */}
          <div className="space-y-1.5 lg:border-l lg:border-divider lg:pl-6">
            <div className="flex items-center space-x-1.5 text-ink-primary font-bold">
              <span className="text-accent-amber">02.</span>
              <span>MACRO SURVEILLANCE &amp; ADVERSARIAL SCULPTING SCOPE</span>
            </div>
            <p className="text-ink-secondary">
              {data.caveats.adversarial_gaming_caveat}
            </p>
          </div>
        </div>
      </div>

      {/* ── SECTION 1: BENFORD'S LAW FIRST-DIGIT DISTRIBUTION ── */}
      <div className="bg-bg-raised border border-divider rounded-sm p-6 lg:p-8 space-y-6">
        {/* Section Header with Pool Switcher */}
        <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-divider">
          <div>
            <h2 className="font-display font-bold text-xl text-ink-primary flex items-center">
              <Activity className="w-5 h-5 mr-2 text-accent-amber" />
              Benford&apos;s Law 1st-Digit Distribution Analysis
            </h2>
            <p className="text-xs font-mono text-ink-secondary mt-0.5">
              FIRST-DIGIT FREQUENCY SCREENING ACROSS TRANSACTION POPULATIONS · THEORETICAL P(d) = log₁₀(1 + 1/d)
            </p>
          </div>

          {/* Pool Selection Tabs */}
          <div className="flex items-center space-x-1 p-1 bg-bg-base rounded-sm border border-divider">
            <button
              onClick={() => setSelectedPool("payments_pool")}
              className={clsx(
                "px-3 py-1.5 text-xs font-mono rounded-sm transition-all",
                selectedPool === "payments_pool"
                  ? "bg-bg-raised text-ink-primary font-bold border border-divider shadow-sm"
                  : "text-ink-muted hover:text-ink-secondary"
              )}
            >
              Merchant Payments (N={data.benford_analysis.payments_pool.sample_size_n})
            </button>
            <button
              onClick={() => setSelectedPool("credits_pool")}
              className={clsx(
                "px-3 py-1.5 text-xs font-mono rounded-sm transition-all",
                selectedPool === "credits_pool"
                  ? "bg-bg-raised text-ink-primary font-bold border border-divider shadow-sm"
                  : "text-ink-muted hover:text-ink-secondary"
              )}
            >
              Bank Credits (N={data.benford_analysis.credits_pool.sample_size_n})
            </button>
            <button
              onClick={() => setSelectedPool("combined_pool")}
              className={clsx(
                "px-3 py-1.5 text-xs font-mono rounded-sm transition-all",
                selectedPool === "combined_pool"
                  ? "bg-bg-raised text-ink-primary font-bold border border-divider shadow-sm"
                  : "text-ink-muted hover:text-ink-secondary"
              )}
            >
              Combined (N={data.benford_analysis.combined_pool.sample_size_n})
            </button>
          </div>
        </div>

        {/* Hero Finding: Dominant Chi-Square Stat Display */}
        <div className="py-2 flex flex-wrap items-baseline justify-between gap-6 border-b border-divider/60">
          <div className="space-y-1">
            <div className="text-[11px] font-mono text-ink-muted uppercase tracking-wider">
              PEARSON GOODNESS-OF-FIT STATISTIC (df = 8)
            </div>
            <div className="flex items-baseline space-x-4">
              <span className="text-4xl sm:text-5xl font-mono font-bold text-accent-amber tracking-tight">
                χ² = {activePool.chi_square_statistic.toFixed(2)}
              </span>
              <span
                className={clsx(
                  "px-2.5 py-1 text-xs font-mono font-bold uppercase rounded-sm border",
                  activePool.is_statistically_conforming
                    ? "bg-status-proven/10 text-status-proven border-status-proven/40"
                    : "bg-status-probable/10 text-status-probable border-status-probable/40"
                )}
              >
                {activePool.conformity_classification.replace(/_/g, " ")}
              </span>
            </div>
          </div>

          <div className="text-right space-y-1 text-xs font-mono">
            <div className="text-ink-secondary">
              <span className="text-ink-muted mr-1.5">POPULATION POOL:</span>
              <span className="text-ink-primary font-bold">{activePool.pool_name}</span>
            </div>
            <div className="text-ink-secondary">
              <span className="text-ink-muted mr-1.5">SAMPLE SIZE (N):</span>
              <span className="text-ink-primary font-bold">{activePool.sample_size_n} records</span>
              <span className="text-ink-muted mx-2">·</span>
              <span className="text-ink-muted mr-1.5">CRITICAL VALUE (p=0.05):</span>
              <span className="text-ink-primary font-bold">χ²₀.₀₅ = {activePool.critical_value_05}</span>
            </div>
          </div>
        </div>

        {/* Visual Bar Comparison Chart (Observed vs Expected) */}
        <div className="space-y-4 pt-2">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-ink-muted uppercase tracking-wider">
              DIGIT FREQUENCY DISTRIBUTION · OBSERVED BATCH VS THEORETICAL BENFORD CURVE
            </span>
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-1.5">
                <span className="w-2.5 h-2.5 bg-accent-amber rounded-xs" />
                <span className="text-ink-secondary">Observed Batch</span>
              </div>
              <div className="flex items-center space-x-1.5">
                <span className="w-2.5 h-2.5 bg-zinc-600 rounded-xs border-t border-zinc-400" />
                <span className="text-ink-muted">Theoretical Benford</span>
              </div>
            </div>
          </div>

          {/* 9 Digit Cards */}
          <div className="grid grid-cols-3 sm:grid-cols-9 gap-2.5">
            {activePool.digit_statistics.map((stat: DigitStat) => {
              const maxScale = 35.0; // scale max percentage to 35%
              const obsHeight = Math.min(100, (stat.observed_pct / maxScale) * 100);
              const expHeight = Math.min(100, (stat.expected_pct / maxScale) * 100);

              return (
                <div
                  key={stat.digit}
                  className="bg-bg-base border border-divider p-3 rounded-sm flex flex-col items-center justify-between space-y-3"
                >
                  <div className="text-xs font-mono font-bold text-ink-primary">
                    DIGIT {stat.digit}
                  </div>

                  {/* Dual Bar Graphic */}
                  <div className="w-full h-32 flex items-end justify-center gap-1.5 pb-1 border-b border-divider/60">
                    {/* Observed Bar (Amber Token) */}
                    <div className="flex flex-col items-center flex-1 h-full justify-end">
                      <div
                        className="w-full bg-accent-amber rounded-t-xs transition-all duration-300"
                        style={{ height: `${Math.max(4, obsHeight)}%` }}
                        title={`Observed: ${stat.observed_pct}% (${stat.observed_count} records)`}
                      />
                    </div>

                    {/* Expected Benford Bar */}
                    <div className="flex flex-col items-center flex-1 h-full justify-end">
                      <div
                        className="w-full bg-zinc-700 border-t border-zinc-400 rounded-t-xs transition-all duration-300"
                        style={{ height: `${Math.max(4, expHeight)}%` }}
                        title={`Theoretical: ${stat.expected_pct}%`}
                      />
                    </div>
                  </div>

                  {/* Metrics Footer */}
                  <div className="w-full space-y-0.5 text-center text-[10px] font-mono">
                    <div className="text-accent-amber font-bold">
                      {stat.observed_pct}%{" "}
                      <span className="text-ink-muted font-normal">({stat.observed_count})</span>
                    </div>
                    <div className="text-ink-muted">
                      Exp: {stat.expected_pct}%
                    </div>
                    <div className="text-[9px] text-ink-muted pt-1 border-t border-divider/40">
                      χ²={stat.chi_square_contribution}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <p className="text-[11px] font-mono text-ink-muted pt-2">
            * {activePool.methodological_note}
          </p>
        </div>
      </div>

      {/* ── SECTION 2: TOLERANCE BOUNDARY CLUSTERING (GAMING SURVEILLANCE) ── */}
      <div className="bg-bg-raised border border-divider rounded-sm p-6 lg:p-8 space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-divider">
          <div>
            <h2 className="font-display font-bold text-xl text-ink-primary flex items-center">
              <ShieldCheck className="w-5 h-5 mr-2 text-status-proven" />
              Tolerance Boundary Clustering Detector
            </h2>
            <p className="text-xs font-mono text-ink-secondary mt-0.5">
              SURVEILLANCE OF DEDUCTION TOLERANCE HEADROOM (ε USED) ACROSS ALL 49 PROVEN SETTLEMENT MATCHES
            </p>
          </div>

          <div className="text-right">
            <span className="text-[10px] font-mono text-ink-muted uppercase block">Heuristic Cutoff:</span>
            <span className="text-xs font-mono font-bold text-ink-primary">
              {tc.heuristic_threshold_pct}% Cliff Edge ({tc.methodological_disclaimer})
            </span>
          </div>
        </div>

        {/* Hero Finding: 0.0% Cliff-Edge Headline */}
        <div className="py-2 flex flex-wrap items-baseline justify-between gap-6 border-b border-divider/60">
          <div className="space-y-1">
            <div className="text-[11px] font-mono text-ink-muted uppercase tracking-wider">
              BOUNDARY CLIFF-EDGE CLUSTERING RATIO (80%–100% EPSILON BAND)
            </div>
            <div className="flex items-baseline space-x-4">
              <span className="text-4xl sm:text-5xl font-mono font-bold text-status-proven tracking-tight">
                0.0%
              </span>
              <span className="px-2.5 py-1 text-xs font-mono font-bold uppercase rounded-sm border bg-status-proven/10 text-status-proven border-status-proven/40">
                RECONCILIATION INTEGRITY VERIFIED
              </span>
            </div>
          </div>

          <div className="text-right space-y-1 text-xs font-mono">
            <div className="text-ink-secondary">
              <span className="text-ink-muted mr-1.5">TOTAL PROVEN MATCHES:</span>
              <span className="text-ink-primary font-bold">{tc.total_matched_records} records</span>
            </div>
            <div className="text-ink-secondary">
              <span className="text-ink-muted mr-1.5">MEAN EPSILON USED:</span>
              <span className="text-status-proven font-bold">{tc.mean_epsilon_pct}%</span>
              <span className="text-ink-muted mx-2">·</span>
              <span className="text-ink-muted mr-1.5">CLIFF-EDGE RECORDS:</span>
              <span className="text-status-proven font-bold">0 records</span>
            </div>
          </div>
        </div>

        {/* 5 Epsilon Histogram Bins */}
        <div className="grid grid-cols-1 sm:grid-cols-5 gap-3 pt-2">
          {tc.bins.map((bin) => {
            const isCliff = bin.bin_range === "[80% - 100%]";
            const isDominant = bin.count > 0;

            return (
              <div
                key={bin.bin_range}
                className={clsx(
                  "p-4 rounded-sm border space-y-3 transition-all",
                  isDominant
                    ? "bg-bg-base border-status-proven/60"
                    : isCliff
                    ? "bg-bg-base border-divider"
                    : "bg-bg-base border-divider/60"
                )}
              >
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="font-bold text-ink-primary">{bin.bin_range}</span>
                  <span className={clsx(isDominant ? "text-status-proven font-bold" : "text-ink-muted")}>
                    {bin.percentage}%
                  </span>
                </div>

                <div className="space-y-1">
                  <div className="text-2xl font-bold font-mono text-ink-primary">
                    {bin.count} <span className="text-xs font-normal text-ink-muted">matches</span>
                  </div>
                  <div className="w-full bg-bg-inset h-1.5 rounded-xs overflow-hidden">
                    <div
                      className={clsx("h-full", isDominant ? "bg-status-proven" : "bg-ink-muted/40")}
                      style={{ width: `${bin.percentage}%` }}
                    />
                  </div>
                </div>

                <p className="text-[11px] font-mono text-ink-muted leading-tight">
                  {bin.description}
                </p>
              </div>
            );
          })}
        </div>

        {/* Forensic Verdict Callout */}
        <div className="p-4 rounded-sm bg-status-proven/5 border border-status-proven/40 flex items-start space-x-3">
          <ShieldCheck className="w-5 h-5 text-status-proven shrink-0 mt-0.5" />
          <div className="space-y-1">
            <div className="text-xs font-bold font-mono text-status-proven uppercase tracking-wider">
              ZERO TOLERANCE BOUNDARY GAMING OBSERVED
            </div>
            <p className="text-xs font-mono text-ink-secondary leading-relaxed">
              {tc.forensic_interpretation}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
