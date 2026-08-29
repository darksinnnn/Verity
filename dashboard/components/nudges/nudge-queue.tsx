"use client";

import React, { useEffect, useState } from "react";
import { NudgeDraft, fetchNudges, dispatchNudgeMock } from "@/lib/api-client";
import { MonoText } from "../ui/mono-text";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Send, Mail, MessageSquare, CheckCheck, Clock, ExternalLink } from "lucide-react";
import clsx from "clsx";

export function NudgeQueue() {
  const [nudges, setNudges] = useState<NudgeDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [dispatchedIds, setDispatchedIds] = useState<Record<string, any>>({});
  const [dispatchingId, setDispatchingId] = useState<string | null>(null);

  useEffect(() => {
    fetchNudges()
      .then((res) => setNudges(res.nudges))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  const handleDispatch = async (nudge: NudgeDraft) => {
    setDispatchingId(nudge.exception_id);
    try {
      const receipt = await dispatchNudgeMock(nudge);
      setDispatchedIds((prev) => ({
        ...prev,
        [nudge.exception_id]: receipt,
      }));
    } catch (err) {
      console.error(err);
    } finally {
      setDispatchingId(null);
    }
  };

  if (loading) {
    return (
      <div className="bg-bg-raised border border-divider p-8 text-center text-xs font-mono text-ink-muted rounded-sm">
        DRAFTING TARGETED ACTIONABLE EXCEPTION NOTICES...
      </div>
    );
  }

  return (
    <div className="bg-bg-raised border border-divider rounded-sm p-6 lg:p-8 space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-divider">
        <div>
          <h2 className="font-display font-bold text-xl text-ink-primary flex items-center">
            <Mail className="w-5 h-5 mr-2 text-accent-amber" />
            Actionable Exception Nudge Queue
          </h2>
          <p className="text-xs font-mono text-ink-secondary mt-0.5">
            AUTO-DRAFTED PLAIN-ENGLISH NOTICES FOR COUNTERPARTY RECONCILIATION
          </p>
        </div>
        <div className="text-xs font-mono text-status-probable bg-status-probable/10 px-2 py-1 rounded-sm border border-status-probable/30">
          MOCKED DISPATCH NO-OP (ZERO NETWORK SIDE-EFFECTS)
        </div>
      </div>

      {/* Nudge Cards Grid */}
      <div className="space-y-4">
        {nudges.map((nudge) => {
          const isDispatched = !!dispatchedIds[nudge.exception_id];
          const isDispatching = dispatchingId === nudge.exception_id;
          const isSlack = nudge.channel.includes("Slack");

          return (
            <div
              key={nudge.exception_id}
              className="bg-bg-inset border border-divider p-5 rounded-sm space-y-4 hover:border-ink-muted transition-colors"
            >
              {/* Card Header */}
              <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-divider/60">
                <div className="flex items-center space-x-2.5">
                  {isSlack ? (
                    <MessageSquare className="w-4 h-4 text-accent-amber" />
                  ) : (
                    <Mail className="w-4 h-4 text-status-probable" />
                  )}
                  <span className="text-xs font-mono font-bold text-ink-primary">
                    RECIPIENT: {nudge.recipient_team}
                  </span>
                  <span className="text-[10px] font-mono text-ink-muted px-1.5 py-0.5 bg-bg-base border border-divider rounded-sm">
                    {nudge.channel}
                  </span>
                </div>

                <div className="flex items-center space-x-3">
                  <span className="text-xs font-mono text-ink-muted">
                    REF: <MonoText variant="primary">{nudge.related_record_id}</MonoText>
                  </span>
                  <span className="text-xs font-mono font-bold text-accent-amber">
                    ₹{(nudge.amount_at_risk_paise / 100).toFixed(2)}
                  </span>
                </div>
              </div>

              {/* Subject Line */}
              <div className="text-xs font-mono font-semibold text-ink-primary">
                <span className="text-ink-muted mr-1.5">SUBJECT:</span>
                {nudge.subject}
              </div>

              {/* Draft Message Body */}
              <div className="bg-bg-base p-4 border border-divider rounded-sm text-xs font-mono text-ink-secondary whitespace-pre-wrap leading-relaxed">
                {nudge.message_body}
              </div>

              {/* Suggested Action & Mocked Send Button */}
              <div className="pt-2 flex flex-wrap items-center justify-between gap-3">
                <div className="text-xs font-mono text-ink-muted">
                  SUGGESTED ACTION: <span className="text-ink-secondary font-medium">{nudge.suggested_action}</span>
                </div>

                {isDispatched ? (
                  <div className="flex items-center space-x-2 text-xs font-mono text-status-proven bg-status-proven/10 px-3 py-1.5 border border-status-proven/30 rounded-sm">
                    <CheckCheck className="w-4 h-4" />
                    <span>MOCKED DISPATCH RECORDED ({dispatchedIds[nudge.exception_id]?.dispatched_at?.slice(11, 19)})</span>
                  </div>
                ) : (
                  <Button
                    variant="amber"
                    size="sm"
                    disabled={isDispatching}
                    onClick={() => handleDispatch(nudge)}
                  >
                    <Send className="w-3.5 h-3.5 mr-1.5" />
                    {isDispatching ? "Logging Mock Dispatch..." : "Dispatch Nudge (UI Proof Mock)"}
                  </Button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
