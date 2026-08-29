"use client";

import React, { useEffect, useState } from "react";
import { AuditTrailData, fetchAuditTrail, runTamperDemo } from "@/lib/api-client";
import { MonoText } from "../ui/mono-text";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { motion, AnimatePresence } from "framer-motion";
import { ShieldCheck, ShieldAlert, Link, Lock, RefreshCw, AlertTriangle, Key } from "lucide-react";
import clsx from "clsx";

export function HashChainView() {
  const [data, setData] = useState<AuditTrailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [tamperState, setTamperState] = useState<{
    active: boolean;
    tamperedIndex: number | null;
    message: string | null;
    targetId: string | null;
  }>({ active: false, tamperedIndex: null, message: null, targetId: null });
  const [tamperLoading, setTamperLoading] = useState(false);

  const loadChain = () => {
    setLoading(true);
    fetchAuditTrail()
      .then((res) => {
        setData(res);
        setTamperState({ active: false, tamperedIndex: null, message: null, targetId: null });
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadChain();
  }, []);

  const handleSimulateTamper = async () => {
    setTamperLoading(true);
    try {
      const res = await runTamperDemo();
      setTamperState({
        active: true,
        tamperedIndex: res.tampered_index,
        message: res.message,
        targetId: res.target_entry_id,
      });
    } catch (err) {
      console.error(err);
    } finally {
      setTamperLoading(false);
    }
  };

  if (loading && !data) {
    return (
      <div className="bg-bg-raised border border-divider p-8 text-center text-xs font-mono text-ink-muted rounded-sm">
        VERIFYING SHA-256 APPEND-ONLY HASH CHAIN INTEGRITY...
      </div>
    );
  }

  const isValid = !tamperState.active && (data?.is_valid ?? true);

  return (
    <div className="bg-bg-raised border border-divider rounded-sm p-6 lg:p-8 space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-divider">
        <div>
          <h2 className="font-display font-bold text-xl text-ink-primary flex items-center">
            <Lock className="w-5 h-5 mr-2 text-accent-amber" />
            Cryptographic Audit Trail (Append-Only Hash Chain)
          </h2>
          <p className="text-xs font-mono text-ink-secondary mt-0.5">
            SHA-256 LINKED VERDICT LEDGER (TOTAL IMMUTABLE ENTRIES: {data?.total_entries || 0})
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center space-x-3">
          <Button
            variant={tamperState.active ? "primary" : "danger"}
            size="sm"
            onClick={tamperState.active ? loadChain : handleSimulateTamper}
            disabled={tamperLoading}
          >
            {tamperState.active ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Restore Valid Chain View
              </>
            ) : (
              <>
                <AlertTriangle className="w-3.5 h-3.5 mr-1.5" /> Simulate In-Memory Tamper Attack
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Chain Status Bar */}
      <div
        className={clsx(
          "p-4 rounded-sm border flex flex-wrap items-center justify-between gap-3 transition-colors",
          isValid
            ? "bg-status-proven/10 border-status-proven/40 text-status-proven"
            : "bg-status-unresolved/15 border-status-unresolved/50 text-status-unresolved"
        )}
      >
        <div className="flex items-center space-x-3">
          {isValid ? (
            <ShieldCheck className="w-5 h-5 shrink-0" />
          ) : (
            <ShieldAlert className="w-5 h-5 shrink-0 animate-bounce" />
          )}
          <div>
            <span className="font-mono text-xs font-bold uppercase tracking-wider block">
              {isValid
                ? "HASH CHAIN INTEGRITY: UNBROKEN & MATHEMATICALLY VERIFIED"
                : "CRYPTOGRAPHIC INTEGRITY FAILURE: HASH MISMATCH DETECTED"}
            </span>
            <span className="text-xs font-mono opacity-80">
              {isValid
                ? `Genesis to Tip (${data?.total_entries || 0} entries) verified with zero unauthorized edits.`
                : tamperState.message || "Simulated tampering severed hash link."}
            </span>
          </div>
        </div>

        <div className="text-right text-xs font-mono">
          <span className="opacity-70 uppercase block text-[10px]">CURRENT CHAIN STATUS</span>
          <span className="font-bold">{isValid ? "100% PROVEN VALID" : "TAMPER SEVERED"}</span>
        </div>
      </div>

      {/* Linked Block Chain Horizontal Visualizer */}
      <div className="space-y-3">
        <div className="flex justify-between items-center text-xs font-mono text-ink-muted">
          <span>INTERACTIVE BLOCK EXPLORER (TOP ENTRIES)</span>
          <span>CHAIN LINK: SHA-256(prev_hash + canonical_json + timestamp)</span>
        </div>

        <div className="overflow-x-auto pb-4 pt-1">
          <div className="flex items-center space-x-3 min-w-max">
            {data?.entries.map((entry, idx) => {
              const isTamperedBlock = tamperState.active && idx === tamperState.tamperedIndex;
              const isDownstreamBroken = tamperState.active && tamperState.tamperedIndex !== null && idx > tamperState.tamperedIndex;

              return (
                <React.Fragment key={entry.id}>
                  {/* Cryptographic Block */}
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{
                      opacity: 1,
                      scale: 1,
                      borderColor: isTamperedBlock
                        ? "var(--status-unresolved)"
                        : isDownstreamBroken
                        ? "var(--divider)"
                        : "var(--divider)",
                    }}
                    transition={{ duration: 0.2, delay: idx * 0.04 }}
                    className={clsx(
                      "w-64 bg-bg-inset border p-3.5 rounded-sm space-y-2 text-xs font-mono transition-all",
                      isTamperedBlock
                        ? "border-2 border-status-unresolved bg-status-unresolved/10 ring-2 ring-status-unresolved/20"
                        : isDownstreamBroken
                        ? "opacity-60 border-divider border-dashed"
                        : "hover:border-ink-muted border-divider"
                    )}
                  >
                    {/* Block Header */}
                    <div className="flex justify-between items-center text-[10px] pb-1.5 border-b border-divider/60">
                      <span className="font-bold text-accent-amber">BLOCK #{idx}</span>
                      <span className="text-ink-muted">{entry.created_at?.slice(11, 19)}</span>
                    </div>

                    {/* Event Type */}
                    <div className="font-bold text-ink-primary truncate">
                      {isTamperedBlock ? "[FORGED OVERRIDE]" : entry.event_type}
                    </div>

                    {/* Hashes */}
                    <div className="space-y-1 text-[10px]">
                      <div>
                        <span className="text-ink-muted block">PREV HASH:</span>
                        <span className="text-ink-secondary truncate block">
                          {entry.previous_hash === "GENESIS" ? "GENESIS" : entry.previous_hash.slice(0, 16) + "..."}
                        </span>
                      </div>
                      <div>
                        <span className="text-ink-muted block">ENTRY HASH:</span>
                        <span className={clsx("truncate block font-bold", isTamperedBlock ? "text-status-unresolved" : "text-status-proven")}>
                          {isTamperedBlock ? "HASH_MISMATCH_DETECTED" : entry.entry_hash.slice(0, 16) + "..."}
                        </span>
                      </div>
                    </div>

                    {/* Footer Status */}
                    <div className="pt-1.5 border-t border-divider/60 flex justify-between items-center text-[10px]">
                      <span className="text-ink-muted">{entry.id}</span>
                      <span className={isTamperedBlock ? "text-status-unresolved font-bold" : "text-status-proven"}>
                        {isTamperedBlock ? "TAMPERED" : "SEALED"}
                      </span>
                    </div>
                  </motion.div>

                  {/* Hash Link Connector */}
                  {idx < (data?.entries.length || 0) - 1 && (
                    <div className="flex items-center text-ink-muted shrink-0 px-0.5">
                      {isDownstreamBroken ? (
                        <span className="text-status-unresolved font-bold font-mono text-xs px-1 bg-status-unresolved/20 rounded-sm">
                          ✕ BROKEN
                        </span>
                      ) : (
                        <Link className="w-4 h-4 text-status-proven/70" />
                      )}
                    </div>
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>
      </div>

      {/* Forensic Disclosure Note */}
      <div className="p-4 bg-bg-base border border-divider rounded-sm text-xs font-mono text-ink-secondary leading-relaxed">
        <span className="text-accent-amber font-semibold block mb-1">EVIDENTIARY GUARANTEE & THREAT MODEL:</span>
        Verity's cryptographic hash chain provides verifiable tamper evidence against unilateral row modification, backdating, and record deletion. The simulation above clones the current chain into an isolated in-memory scratchpad and verifies that any unauthorized database edit immediately severs cryptographic verification downstream.
      </div>
    </div>
  );
}
