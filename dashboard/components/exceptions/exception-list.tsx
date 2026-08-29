"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { ExceptionItem } from "@/lib/api-client";
import { Badge } from "../ui/badge";
import { MonoText } from "../ui/mono-text";
import { ExceptionDrawer } from "./exception-drawer";
import { ChevronDown, ChevronUp, AlertOctagon, Filter } from "lucide-react";
import clsx from "clsx";

interface ExceptionListProps {
  exceptions: ExceptionItem[];
  onTraceLineage?: (recordId: string) => void;
  onQueryQA?: (recordId: string, queryPrompt?: string) => void;
}

export function ExceptionList({ exceptions, onTraceLineage, onQueryQA }: ExceptionListProps) {
  const [expandedId, setExpandedId] = useState<string | null>(exceptions[0]?.id || null);
  const [filterStatus, setFilterStatus] = useState<string>("ALL");

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  const filteredExceptions = exceptions.filter((e) => {
    if (filterStatus === "ALL") return true;
    return e.status === filterStatus;
  });

  const getBorderColor = (status: string) => {
    if (status === "PROVEN") return "border-l-status-proven";
    if (status === "PROBABLE") return "border-l-status-probable";
    return "border-l-status-unresolved";
  };

  return (
    <div className="space-y-4">
      {/* Header & Filter Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-divider">
        <div>
          <h2 className="font-display font-bold text-xl text-ink-primary flex items-center">
            <AlertOctagon className="w-5 h-5 mr-2 text-accent-amber" />
            Active Reconciliation Exceptions
          </h2>
          <p className="text-xs font-mono text-ink-secondary mt-0.5">
            RANKED BY ₹-AMOUNT-AT-RISK (STRICT ABDUCTIVE REASONING)
          </p>
        </div>

        {/* Status Filter Tabs */}
        <div className="flex items-center space-x-1 bg-bg-inset border border-divider p-1 rounded-sm text-xs font-mono">
          <button
            onClick={() => setFilterStatus("ALL")}
            className={clsx(
              "px-2.5 py-1 rounded-sm transition-colors",
              filterStatus === "ALL" ? "bg-bg-raised text-ink-primary font-medium" : "text-ink-muted hover:text-ink-secondary"
            )}
          >
            ALL ({exceptions.length})
          </button>
          <button
            onClick={() => setFilterStatus("PROBABLE")}
            className={clsx(
              "px-2.5 py-1 rounded-sm transition-colors",
              filterStatus === "PROBABLE" ? "bg-bg-raised text-status-probable font-medium" : "text-ink-muted hover:text-status-probable"
            )}
          >
            PROBABLE
          </button>
          <button
            onClick={() => setFilterStatus("UNRESOLVED")}
            className={clsx(
              "px-2.5 py-1 rounded-sm transition-colors",
              filterStatus === "UNRESOLVED" ? "bg-bg-raised text-status-unresolved font-medium" : "text-ink-muted hover:text-status-unresolved"
            )}
          >
            UNRESOLVED
          </button>
        </div>
      </div>

      {/* Exception Case-File Entries (Staggered Entrance Animation) */}
      <div className="space-y-3">
        {filteredExceptions.map((exc, index) => {
          const isExpanded = expandedId === exc.id;
          const statusBorder = getBorderColor(exc.status);

          return (
            <motion.div
              key={exc.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: index * 0.08, ease: "easeOut" }}
              className="bg-bg-raised border border-divider rounded-sm overflow-hidden transition-all hover:border-ink-muted/50"
            >
              {/* Main Summary Row */}
              <div
                onClick={() => toggleExpand(exc.id)}
                className={clsx(
                  "p-4 lg:p-5 flex flex-wrap items-center justify-between gap-4 cursor-pointer select-none border-l-4 transition-colors",
                  statusBorder,
                  isExpanded ? "bg-bg-raised" : "hover:bg-bg-inset/40"
                )}
              >
                {/* Left: Rank, ID, Record Ref */}
                <div className="flex items-center space-x-3 sm:space-x-4">
                  <span className="font-mono text-xs font-bold text-ink-muted w-6">
                    #{index + 1}
                  </span>
                  <div className="space-y-1">
                    <div className="flex items-center space-x-2.5">
                      <MonoText variant="primary" className="text-sm font-semibold">
                        {exc.related_record_id}
                      </MonoText>
                      <Badge status={exc.status} />
                    </div>
                    <p className="text-xs text-ink-secondary line-clamp-1 max-w-md lg:max-w-xl">
                      {exc.explanation_text}
                    </p>
                  </div>
                </div>

                {/* Right: Amount at Risk & Expand Toggle */}
                <div className="flex items-center space-x-6 ml-auto sm:ml-0">
                  <div className="text-right">
                    <span className="text-[10px] font-mono uppercase text-ink-muted block">
                      AT RISK (PAISE: {exc.amount_at_risk_paise})
                    </span>
                    <MonoText
                      variant={exc.status === "UNRESOLVED" ? "crimson" : "gold"}
                      className="text-base sm:text-lg font-bold"
                    >
                      ₹{exc.amount_at_risk_rs.toFixed(2)}
                    </MonoText>
                  </div>
                  <div className="text-ink-muted hover:text-ink-primary transition-colors">
                    {isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
                  </div>
                </div>
              </div>

              {/* Expandable Case-File Drawer */}
              {isExpanded && (
                <ExceptionDrawer
                  exception={exc}
                  onTraceLineage={onTraceLineage}
                  onQueryQA={onQueryQA}
                />
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
