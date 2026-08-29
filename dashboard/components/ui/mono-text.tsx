import React from "react";
import clsx from "clsx";

interface MonoTextProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "primary" | "secondary" | "muted" | "amber" | "green" | "gold" | "crimson";
}

export function MonoText({
  children,
  className,
  variant = "primary",
  ...props
}: MonoTextProps) {
  const colorMap = {
    primary: "text-ink-primary",
    secondary: "text-ink-secondary",
    muted: "text-ink-muted",
    amber: "text-accent-amber",
    green: "text-status-proven",
    gold: "text-status-probable",
    crimson: "text-status-unresolved",
  };

  return (
    <span
      className={clsx(
        "font-mono font-medium tracking-tight",
        colorMap[variant],
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}
