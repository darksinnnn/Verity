"use client";

import React from "react";
import { ExceptionItem } from "@/lib/api-client";
import { Badge } from "../ui/badge";
import { MonoText } from "../ui/mono-text";
import { Button } from "../ui/button";
import { FileText, ArrowRight, CheckCircle2, AlertCircle } from "lucide-react";

interface ExceptionDrawerProps {
  exception: ExceptionItem;
  onTraceLineage?: (recordId: string) => void;
  onQueryQA?: (recordId: string, queryPrompt?: string) => void;
}

export function ExceptionDrawer({ exception, onTraceLineage, onQueryQA }: ExceptionDrawerProps) {
  const { related_record_id, status, explanation_text, hypotheses, amount_at_risk_rs } = exception;

  return (
    <div className="bg-bg-inset border-t border-divider p-5 space-y-5 rounded-b-sm animate-in fade-in duration-200">
      {/* Evidence Finding */}
      <div className="space-y-1.5">
        <span className="text-xs font-mono uppercase tracking-wider text-ink-muted flex items-center">
          <FileText className="w-3.5 h-3.5 mr-1 text-accent-amber" /> FORENSIC EXPLANATION & AUDIT VERDICT
        </span>
        <p className="text-sm text-ink-primary leading-relaxed bg-bg-base/60 p-3.5 border border-divider rounded-sm font-sans">
          {explanation_text}
        </p>
      </div>

      {/* Abductive Hypotheses Breakdown */}
      {hypotheses && hypotheses.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase tracking-wider text-ink-muted">
              ABDUCTIVE HYPOTHESES (RANKED BY PLAUSIBILITY)
            </span>
            <span className="text-xs font-mono text-ink-muted">NO ARBITRARY CONFIDENCE SCORES</span>
          </div>

          <div className="space-y-2">
            {hypotheses.map((h, idx) => (
              <div
                key={idx}
                className="p-3.5 bg-bg-base border border-divider rounded-sm space-y-2 relative pl-4 border-l-2 border-l-status-probable"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-xs font-mono uppercase font-semibold text-status-probable">
                    HYPOTHESIS #{idx + 1}: {h.category}
                  </span>
                </div>
                <p className="text-sm text-ink-primary font-sans">{h.hypothesis}</p>
                <div className="pt-2 border-t border-divider/60 flex items-start text-xs font-mono text-ink-secondary">
                  <span className="text-accent-amber mr-1.5 font-bold">REQUIRED EVIDENCE:</span>
                  <span>{h.evidence_needed}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action Bar */}
      <div className="pt-3 border-t border-divider flex flex-wrap items-center justify-between gap-3">
        <div className="text-xs font-mono text-ink-muted">
          AMOUNT AT RISK: <MonoText variant="crimson" className="text-sm font-bold">₹{amount_at_risk_rs.toFixed(2)}</MonoText>
        </div>
        <div className="flex items-center space-x-2">
          {onTraceLineage && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => onTraceLineage(related_record_id)}
            >
              Trace Money Lineage <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
            </Button>
          )}
          {onQueryQA && (
            <Button
              variant="amber"
              size="sm"
              onClick={() =>
                onQueryQA(
                  related_record_id,
                  `Why is bank credit ${related_record_id} classified as ${status}? What evidence is missing?`
                )
              }
            >
              Interrogate in Q&A Terminal
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
