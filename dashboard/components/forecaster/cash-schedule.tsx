"use client";

import React, { useEffect, useState } from "react";
import { ForecastReport, fetchForecast } from "@/lib/api-client";
import { MonoText } from "../ui/mono-text";
import { Badge } from "../ui/badge";
import { Calendar, ArrowUpRight, ArrowDownRight, Clock, ShieldAlert } from "lucide-react";

export function CashSchedule() {
  const [forecast, setForecast] = useState<ForecastReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchForecast()
      .then((data) => setForecast(data))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="bg-bg-raised border border-divider p-8 text-center text-xs font-mono text-ink-muted rounded-sm">
        COMPUTING DETERMINISTIC CASH SCHEDULE...
      </div>
    );
  }

  if (!forecast) {
    return (
      <div className="bg-bg-raised border border-divider p-8 text-center text-xs font-mono text-status-unresolved rounded-sm">
        FAILED TO LOAD CASH FORECAST DATA.
      </div>
    );
  }

  const grossInflowsRs = forecast.total_pending_inflows_gross_paise / 100;
  const feesRs = forecast.total_estimated_deductions_paise / 100;
  const netInflowsRs = forecast.total_expected_inflows_net_paise / 100;
  const refundOutflowsRs = forecast.total_pending_outflows_paise / 100;
  const netPositionRs = forecast.net_projected_cash_position_paise / 100;

  return (
    <div className="bg-bg-raised border border-divider rounded-sm p-6 lg:p-8 space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-divider">
        <div>
          <h2 className="font-display font-bold text-xl text-ink-primary flex items-center">
            <Calendar className="w-5 h-5 mr-2 text-accent-amber" />
            Forward Cash Forecaster (Deterministic Exposure)
          </h2>
          <p className="text-xs font-mono text-ink-secondary mt-0.5">
            EXACT PENDING CAPTURED INFLOWS LESS STATUTORY DEDUCTIONS & OUTFLOWS
          </p>
        </div>
        <div className="text-xs font-mono text-ink-muted flex items-center">
          <Clock className="w-3.5 h-3.5 mr-1" />
          <span>GENERATED: {forecast.projection_generated_at?.slice(0, 19).replace("T", " ")}</span>
        </div>
      </div>

      {/* Summary KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-bg-inset border border-divider p-4 rounded-sm space-y-1">
          <span className="text-[11px] font-mono text-ink-muted uppercase">PENDING GROSS INFLOWS</span>
          <div className="text-xl font-mono font-bold text-ink-primary">
            ₹{grossInflowsRs.toFixed(2)}
          </div>
          <span className="text-[10px] font-mono text-ink-secondary">Captured but unsettled</span>
        </div>

        <div className="bg-bg-inset border border-divider p-4 rounded-sm space-y-1">
          <span className="text-[11px] font-mono text-ink-muted uppercase">EST. DEDUCTIONS (MDR/GST/TDS)</span>
          <div className="text-xl font-mono font-bold text-status-probable">
            -₹{feesRs.toFixed(2)}
          </div>
          <span className="text-[10px] font-mono text-ink-secondary">Standard statutory schedule</span>
        </div>

        <div className="bg-bg-inset border border-divider p-4 rounded-sm space-y-1">
          <span className="text-[11px] font-mono text-ink-muted uppercase">PENDING REFUND OUTFLOWS</span>
          <div className="text-xl font-mono font-bold text-status-unresolved">
            -₹{refundOutflowsRs.toFixed(2)}
          </div>
          <span className="text-[10px] font-mono text-ink-secondary">Customer refund obligations</span>
        </div>

        <div className="bg-bg-inset border border-accent-amber/40 p-4 rounded-sm space-y-1">
          <span className="text-[11px] font-mono text-accent-amber uppercase font-semibold">NET PROJECTED CASH</span>
          <div className="text-2xl font-mono font-bold text-accent-amber">
            ₹{netPositionRs.toFixed(2)}
          </div>
          <span className="text-[10px] font-mono text-ink-secondary">Expected liquidity position</span>
        </div>
      </div>

      {/* Daily Settlement Schedule Table */}
      <div className="space-y-3 pt-2">
        <span className="text-xs font-mono uppercase tracking-wider text-ink-muted">
          T+1 / T+2 VALUE-DATE SETTLEMENT SCHEDULE
        </span>
        <div className="overflow-x-auto border border-divider rounded-sm">
          <table className="w-full text-xs font-mono forensic-table text-left">
            <thead className="bg-bg-inset text-ink-muted">
              <tr>
                <th className="p-3">VALUE DATE</th>
                <th className="p-3">GROSS INFLOWS</th>
                <th className="p-3">FEES & TAXES</th>
                <th className="p-3">NET INFLOWS</th>
                <th className="p-3">REFUND OUTFLOWS</th>
                <th className="p-3 text-right">NET CASH POSITION</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-divider bg-bg-base">
              {forecast.daily_projections?.map((dp, idx) => (
                <tr key={idx} className="hover:bg-bg-raised/60 transition-colors">
                  <td className="p-3 font-semibold text-ink-primary">{dp.date}</td>
                  <td className="p-3 text-ink-primary">₹{(dp.gross_inflows_paise / 100).toFixed(2)}</td>
                  <td className="p-3 text-status-probable">-₹{(dp.estimated_fees_paise / 100).toFixed(2)}</td>
                  <td className="p-3 text-status-proven font-medium">₹{(dp.net_inflows_paise / 100).toFixed(2)}</td>
                  <td className="p-3 text-status-unresolved">-₹{(dp.pending_outflows_paise / 100).toFixed(2)}</td>
                  <td className="p-3 text-right font-bold text-accent-amber">
                    ₹{(dp.net_projected_cash_paise / 100).toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Inflow Payment Method Breakdown */}
      <div className="pt-4 border-t border-divider grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="p-4 bg-bg-inset border border-divider rounded-sm space-y-2">
          <span className="text-xs font-mono uppercase text-ink-muted">INFLOWS BY PAYMENT METHOD</span>
          <div className="space-y-1.5 pt-1">
            {Object.entries(forecast.inflows_by_method || {}).map(([method, paise], i) => (
              <div key={i} className="flex justify-between items-center text-xs font-mono">
                <span className="text-ink-secondary">{method}</span>
                <span className="font-bold text-ink-primary">₹{(paise / 100).toFixed(2)}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="p-4 bg-bg-inset border border-divider rounded-sm space-y-2">
          <span className="text-xs font-mono uppercase text-ink-muted">DETERMINISTIC ASSURANCE</span>
          <p className="text-xs text-ink-secondary leading-relaxed font-sans pt-1">
            Calculated strictly from unsettled captured transactions in <MonoText>payments</MonoText> and pending records in <MonoText>refunds</MonoText>. Zero predictive ML extrapolation.
          </p>
        </div>
      </div>
    </div>
  );
}
