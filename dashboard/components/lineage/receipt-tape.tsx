"use client";

import React, { useEffect, useState } from "react";
import { LineageData, fetchLineage } from "@/lib/api-client";
import { MonoText } from "../ui/mono-text";
import { Badge } from "../ui/badge";
import { motion } from "framer-motion";
import {
  Receipt,
  CheckCircle,
  Clock,
  DollarSign,
  Building2,
  ShoppingCart,
  ShieldCheck,
  AlertOctagon,
  AlertTriangle,
} from "lucide-react";
import clsx from "clsx";

interface ReceiptTapeProps {
  initialRecordId?: string;
  onClose?: () => void;
}

export function ReceiptTape({ initialRecordId = "bc_bd9c66b3", onClose }: ReceiptTapeProps) {
  const [recordId, setRecordId] = useState(initialRecordId);
  const [lineage, setLineage] = useState<LineageData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (initialRecordId && initialRecordId !== recordId) {
      setRecordId(initialRecordId);
    }
  }, [initialRecordId]);

  useEffect(() => {
    setLoading(true);
    fetchLineage(recordId)
      .then((data) => setLineage(data))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [recordId]);

  const getStepIcon = (type: string) => {
    switch (type) {
      case "ORDER":
        return <ShoppingCart className="w-4 h-4 text-accent-amber" />;
      case "PAYMENT":
        return <DollarSign className="w-4 h-4 text-status-proven" />;
      case "DEDUCTION":
      case "REFUND":
        return <Clock className="w-4 h-4 text-status-probable" />;
      case "SETTLEMENT":
        return <Receipt className="w-4 h-4 text-ink-primary" />;
      case "BANK_CREDIT":
        return <Building2 className="w-4 h-4 text-status-proven" />;
      default:
        return <CheckCircle className="w-4 h-4 text-ink-muted" />;
    }
  };

  const getStatusDisplay = () => {
    if (!lineage) return null;
    const status = lineage.status || "PROVEN";

    if (status === "UNRESOLVED") {
      return {
        label: lineage.status_label || "UNRESOLVED VARIANCE — NO CORRESPONDING PAYMENT OBLIGATION",
        colorVariant: "crimson" as const,
        textColor: "text-status-unresolved",
        borderColor: "border-status-unresolved/50",
        bgColor: "bg-status-unresolved/10",
        Icon: AlertOctagon,
      };
    } else if (status === "PROBABLE") {
      return {
        label: lineage.status_label || "PROBABLE VARIANCE — REQUIRES DOCUMENTARY EVIDENCE",
        colorVariant: "gold" as const,
        textColor: "text-status-probable",
        borderColor: "border-status-probable/50",
        bgColor: "bg-status-probable/10",
        Icon: AlertTriangle,
      };
    } else {
      return {
        label: lineage.status_label || "FINAL RECONCILED CLEARING BALANCE",
        colorVariant: "green" as const,
        textColor: "text-status-proven",
        borderColor: "border-status-proven/50",
        bgColor: "bg-status-proven/10",
        Icon: ShieldCheck,
      };
    }
  };

  const statusInfo = getStatusDisplay();

  return (
    <div className="bg-bg-raised border border-divider rounded-sm p-6 lg:p-8 space-y-6">
      {/* Tape Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-divider">
        <div>
          <h2 className="font-display font-bold text-xl text-ink-primary flex items-center">
            <Receipt className="w-5 h-5 mr-2 text-accent-amber" />
            Transaction Lineage Tape
          </h2>
          <p className="text-xs font-mono text-ink-secondary mt-0.5">
            STEP-BY-STEP DOUBLE-ENTRY RUNNING BALANCE TRACE
          </p>
        </div>

        {/* Record Quick Selector */}
        <div className="flex items-center space-x-2">
          <span className="text-xs font-mono text-ink-muted">INSPECT RECORD:</span>
          <select
            value={recordId}
            onChange={(e) => setRecordId(e.target.value)}
            className="bg-bg-inset border border-divider text-ink-primary text-xs font-mono px-3 py-1.5 rounded-sm focus:border-accent-amber focus:outline-none max-w-[280px]"
          >
            <optgroup label="PROVEN CLEAN MATCHES">
              <option value="bc_bd9c66b3">bc_bd9c66b3 (Proven Settlement ₹3,336.45)</option>
              <option value="bc_06cb0fb3">bc_06cb0fb3 (Proven Settlement ₹2,859.87)</option>
              <option value="bc_17be3111">bc_17be3111 (Proven Settlement ₹3,633.93)</option>
            </optgroup>
            <optgroup label="EXCEPTION CASE FILES">
              <option value="bc_4eea04e7">bc_4eea04e7 (Duplicate Extraneous Credit ₹531.52)</option>
              <option value="bc_dd56cc94">bc_dd56cc94 (TDS Rate Variance ₹9.00)</option>
              <option value="bc_f94d6204">bc_f94d6204 (Refund Recovery ₹200.00)</option>
              <option value="bc_33173470">bc_33173470 (Unexplained Gap ₹150.00)</option>
              <option value="bc_c991603f">bc_c991603f (Missing Ledger Gap ₹241.60)</option>
            </optgroup>
          </select>
        </div>
      </div>

      {/* Ledger Tape Strip Visualizer */}
      {loading ? (
        <div className="p-12 text-center text-xs font-mono text-ink-muted">
          COMPUTING DOUBLE-ENTRY LINEAGE TRACE FROM SQLITE...
        </div>
      ) : !lineage || lineage.steps.length === 0 ? (
        <div className="p-12 text-center text-xs font-mono text-status-unresolved">
          NO LINEAGE TRACE FOUND FOR {recordId}
        </div>
      ) : (
        <div className="max-w-2xl mx-auto py-2 relative">
          {/* Animated vertical connecting line */}
          <div className="absolute left-[27px] top-6 bottom-6 w-[2px] bg-divider" />

          <div className="space-y-5">
            {lineage.steps.map((step, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.25, delay: idx * 0.06 }}
                className="relative flex items-start space-x-4 group"
              >
                {/* Step Node Circle */}
                <div className="relative z-10 w-14 h-14 rounded-full bg-bg-inset border border-divider flex items-center justify-center group-hover:border-accent-amber transition-colors shrink-0">
                  {getStepIcon(step.step_type)}
                </div>

                {/* Receipt Segment Box */}
                <div className="flex-1 bg-bg-inset border border-divider p-4 rounded-sm space-y-2 group-hover:border-ink-muted transition-colors">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-mono font-bold text-ink-primary">
                        {step.step_name}
                      </span>
                      <span className="text-[10px] font-mono text-ink-muted px-1.5 py-0.5 bg-bg-base border border-divider rounded-sm">
                        {step.date}
                      </span>
                    </div>

                    {/* Amount Change */}
                    {step.amount_change_paise !== 0 && (
                      <span
                        className={clsx(
                          "text-xs font-mono font-bold",
                          step.amount_change_paise > 0 ? "text-status-proven" : "text-status-unresolved"
                        )}
                      >
                        {step.amount_change_paise > 0 ? "+" : ""}
                        ₹{(step.amount_change_paise / 100).toFixed(2)}
                      </span>
                    )}
                  </div>

                  {/* Identifier & Running Balance */}
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-accent-amber font-semibold">{step.entity_id}</span>
                    <div className="text-right">
                      <span className="text-[10px] text-ink-muted uppercase mr-1.5">RUNNING BALANCE:</span>
                      <MonoText variant="primary" className="font-bold">
                        ₹{(step.running_balance_paise / 100).toFixed(2)}
                      </MonoText>
                    </div>
                  </div>

                  <p className="text-xs text-ink-secondary pt-1 border-t border-divider/60 font-sans">
                    {step.details}
                  </p>
                </div>
              </motion.div>
            ))}
          </div>

          {/* Tape Contextual Footer (Status Aware) */}
          {statusInfo && (
            <div
              className={clsx(
                "mt-8 p-4 border rounded-sm flex flex-wrap items-center justify-between gap-3 text-xs font-mono",
                statusInfo.borderColor,
                statusInfo.bgColor
              )}
            >
              <div className="flex items-center space-x-2">
                <statusInfo.Icon className={clsx("w-4 h-4 shrink-0", statusInfo.textColor)} />
                <span className={clsx("font-bold uppercase tracking-wider", statusInfo.textColor)}>
                  {statusInfo.label}
                </span>
              </div>
              <MonoText variant={statusInfo.colorVariant} className="text-base font-bold">
                ₹{(lineage.final_reconciled_balance_paise / 100).toFixed(2)}
              </MonoText>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
