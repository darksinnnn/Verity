import React from "react";
import clsx from "clsx";

export type StatusType = "PROVEN" | "PROBABLE" | "UNRESOLVED" | "NEUTRAL" | "AMBER";

interface BadgeProps {
  status: StatusType;
  label?: string;
  className?: string;
}

export function Badge({ status, label, className }: BadgeProps) {
  const displayLabel = label || status;

  const styleMap: Record<StatusType, string> = {
    PROVEN: "bg-status-proven/15 text-status-proven border-status-proven/30",
    PROBABLE: "bg-status-probable/15 text-status-probable border-status-probable/30",
    UNRESOLVED: "bg-status-unresolved/15 text-status-unresolved border-status-unresolved/30",
    AMBER: "bg-accent-amber/15 text-accent-amber border-accent-amber/30",
    NEUTRAL: "bg-bg-inset text-ink-secondary border-divider",
  };

  return (
    <span
      className={clsx(
        "inline-flex items-center px-2 py-0.5 text-xs font-mono font-medium uppercase tracking-wider border rounded-sm",
        styleMap[status],
        className
      )}
    >
      <span className="w-1.5 h-1.5 rounded-full mr-1.5 currentColor" style={{ backgroundColor: "currentColor" }} />
      {displayLabel}
    </span>
  );
}
