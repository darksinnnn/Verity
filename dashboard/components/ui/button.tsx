import React from "react";
import clsx from "clsx";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost" | "amber";
  size?: "sm" | "md" | "lg";
}

export function Button({
  children,
  className,
  variant = "primary",
  size = "md",
  disabled,
  ...props
}: ButtonProps) {
  const sizeMap = {
    sm: "px-2.5 py-1 text-xs font-mono",
    md: "px-4 py-2 text-sm font-medium",
    lg: "px-5 py-2.5 text-base font-medium",
  };

  const variantMap = {
    primary: "bg-bg-inset border border-divider text-ink-primary hover:border-ink-secondary hover:bg-bg-raised",
    secondary: "bg-transparent border border-divider text-ink-secondary hover:text-ink-primary hover:border-ink-muted",
    amber: "bg-accent-amber/20 border border-accent-amber/50 text-accent-amber hover:bg-accent-amber/30",
    danger: "bg-status-unresolved/20 border border-status-unresolved/50 text-status-unresolved hover:bg-status-unresolved/30",
    ghost: "bg-transparent text-ink-secondary hover:text-ink-primary hover:bg-bg-inset",
  };

  return (
    <button
      className={clsx(
        "inline-flex items-center justify-center rounded-sm transition-all focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed",
        sizeMap[size],
        variantMap[variant],
        className
      )}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
}
