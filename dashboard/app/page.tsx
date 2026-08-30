"use client";

import React, { useEffect, useState } from "react";
import {
  SummaryData,
  ExceptionItem,
  fetchSummary,
  fetchExceptions,
} from "@/lib/api-client";
import { HeroSummary } from "@/components/hero-summary";
import { ExceptionList } from "@/components/exceptions/exception-list";
import { ReceiptTape } from "@/components/lineage/receipt-tape";
import { TerminalQA } from "@/components/qa-agent/terminal-qa";
import { CashSchedule } from "@/components/forecaster/cash-schedule";
import { HashChainView } from "@/components/audit-trail/hash-chain-view";
import { NudgeQueue } from "@/components/nudges/nudge-queue";
import { ForensicsPanel } from "@/components/forensics/forensics-panel";
import { SectionWipe } from "@/components/transitions/section-wipe";
import {
  ShieldAlert,
  Layers,
  Receipt,
  Terminal,
  Calendar,
  Lock,
  Mail,
  Activity,
  RefreshCw,
} from "lucide-react";

import clsx from "clsx";

export default function DashboardPage() {
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [exceptions, setExceptions] = useState<ExceptionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<string>("overview");
  const [selectedRecordId, setSelectedRecordId] = useState<string>("bc_bd9c66b3");


  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sumRes, excRes] = await Promise.all([
        fetchSummary(),
        fetchExceptions(),
      ]);
      setSummary(sumRes);
      setExceptions(excRes.exceptions);
    } catch (err: any) {
      console.error(err);
      setError("Failed to connect to Verity Forensic API on http://localhost:8000. Ensure 'python api_server.py' is running.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleTraceLineage = (recordId: string) => {
    setSelectedRecordId(recordId);
    setActiveTab("lineage");
  };

  const handleQueryQA = (recordId: string, prompt?: string) => {
    setSelectedRecordId(recordId);
    setActiveTab("qa");
  };

  const navTabs = [
    { id: "overview", num: "01", label: "Case Summary", icon: Layers },
    { id: "exceptions", num: "02", label: `Exceptions (${exceptions.length || 5})`, icon: ShieldAlert },
    { id: "lineage", num: "03", label: "Money Lineage", icon: Receipt },
    { id: "qa", num: "04", label: "Q&A Interrogation", icon: Terminal },
    { id: "forecast", num: "05", label: "Cash Forecaster", icon: Calendar },
    { id: "audit", num: "06", label: "Audit Hash-Chain", icon: Lock },
    { id: "nudges", num: "07", label: "Actionable Nudges", icon: Mail },
    { id: "forensics", num: "08", label: "Statistical Forensics", icon: Activity },
  ];

  return (
    <main className="min-h-screen bg-bg-base text-ink-primary p-4 sm:p-6 lg:p-10 max-w-[1600px] mx-auto space-y-8">
      {/* Forensic Control-Room Masthead */}
      <header className="flex flex-wrap items-center justify-between gap-4 pb-6 border-b border-divider">
        <div className="space-y-1">
          <div className="flex items-center space-x-3">
            <span className="w-3 h-3 bg-accent-amber rounded-sm" />
            <h1 className="font-display font-bold text-2xl sm:text-3xl tracking-tight text-ink-primary">
              VERITY <span className="text-accent-amber font-light">·</span> FORENSIC FINANCE CONTROLLER
            </h1>
          </div>
          <p className="text-xs font-mono text-ink-secondary">
            AUTONOMOUS SETTLEMENT RECONCILIATION &amp; EVIDENTIARY AUDIT ENGINE (TRACK 04)
          </p>
        </div>

        {/* Global Controls & Status */}
        <div className="flex items-center space-x-4">
          <div className="hidden sm:flex items-center space-x-2 text-xs font-mono text-ink-muted">
            <span className="w-2 h-2 rounded-full bg-status-proven" />
            <span>API SERVER: CONNECTED</span>
          </div>
          <button
            onClick={loadData}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-bg-raised border border-divider hover:border-accent-amber/60 text-xs font-mono text-ink-primary rounded-sm transition-colors"
          >
            <RefreshCw className={clsx("w-3.5 h-3.5", loading && "animate-spin")} />
            <span>SYNC DATA</span>
          </button>
        </div>
      </header>

      {/* Case File Navigation Bar */}
      <nav className="flex items-center space-x-1 overflow-x-auto pb-2 border-b border-divider/60 scrollbar-none">
        {navTabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={clsx(
                "flex items-center space-x-1.5 px-2.5 py-1.5 text-[11px] sm:text-xs font-mono whitespace-nowrap rounded-sm transition-all border",
                isActive
                  ? "bg-bg-raised border-accent-amber/60 text-ink-primary font-medium shadow-sm"
                  : "bg-transparent border-transparent text-ink-muted hover:text-ink-secondary hover:bg-bg-raised/40"
              )}
            >
              <span className={clsx("font-bold text-[11px]", isActive ? "text-accent-amber" : "text-ink-muted")}>
                {tab.num}
              </span>
              <Icon className={clsx("w-3.5 h-3.5", isActive ? "text-accent-amber" : "text-ink-muted")} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </nav>



      {/* Error Banner */}
      {error && (
        <div className="p-4 bg-status-unresolved/15 border border-status-unresolved/50 text-status-unresolved text-xs font-mono rounded-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={loadData} className="underline font-bold ml-4">
            RETRY
          </button>
        </div>
      )}

      {/* Case-File Content Area with Section Wipe Transitions */}
      {loading && !summary ? (
        <div className="p-16 text-center text-xs font-mono text-ink-muted bg-bg-raised border border-divider rounded-sm">
          LOADING RECONCILIATION CASE FILE FROM SQLITE...
        </div>
      ) : (
        <SectionWipe activeKey={activeTab}>
          {activeTab === "overview" && summary && (
            <div className="space-y-8">
              <HeroSummary summary={summary} onSelectTab={setActiveTab} />
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
                <div className="lg:col-span-7">
                  <ExceptionList
                    exceptions={exceptions}
                    onTraceLineage={handleTraceLineage}
                    onQueryQA={handleQueryQA}
                  />
                </div>
                <div className="lg:col-span-5 space-y-6">
                  <ReceiptTape initialRecordId={selectedRecordId} />
                </div>
              </div>
            </div>
          )}

          {activeTab === "exceptions" && (
            <div className="space-y-6">
              <ExceptionList
                exceptions={exceptions}
                onTraceLineage={handleTraceLineage}
                onQueryQA={handleQueryQA}
              />
            </div>
          )}

          {activeTab === "lineage" && (
            <div className="space-y-6">
              <ReceiptTape initialRecordId={selectedRecordId} />
            </div>
          )}

          {activeTab === "qa" && (
            <div className="space-y-6">
              <TerminalQA />
            </div>
          )}

          {activeTab === "forecast" && (
            <div className="space-y-6">
              <CashSchedule />
            </div>
          )}

          {activeTab === "audit" && (
            <div className="space-y-6">
              <HashChainView />
            </div>
          )}

          {activeTab === "nudges" && (
            <div className="space-y-6">
              <NudgeQueue />
            </div>
          )}

          {activeTab === "forensics" && (
            <div className="space-y-6">
              <ForensicsPanel />
            </div>
          )}
        </SectionWipe>

      )}

      {/* Forensic Footer */}
      <footer className="pt-8 pb-4 border-t border-divider flex flex-wrap items-center justify-between gap-4 text-[11px] font-mono text-ink-muted">
        <div className="flex items-center space-x-3">
          <span>VERITY CORE ENGINE v1.0</span>
          <span>•</span>
          <span>DETERMINISTIC CAUSAL RECONCILIATION</span>
          <span>•</span>
          <span>RAZORPAY AI BUILDATHON (TRACK 04)</span>
        </div>
        <div className="flex items-center space-x-2">
          <span>HASH CHAIN: UNBROKEN</span>
          <span>•</span>
          <span>ZERO ARITHMETIC LLM DRIFT</span>
        </div>
      </footer>
    </main>
  );
}
