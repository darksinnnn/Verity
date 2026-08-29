import React from "react";
import clsx from "clsx";

interface PanelProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "raised" | "inset" | "base";
  bordered?: boolean;
}

export function Panel({
  children,
  className,
  variant = "raised",
  bordered = true,
  ...props
}: PanelProps) {
  const bgClass =
    variant === "raised"
      ? "bg-bg-raised"
      : variant === "inset"
      ? "bg-bg-inset"
      : "bg-bg-base";

  return (
    <div
      className={clsx(
        bgClass,
        bordered && "border border-divider",
        "rounded-sm p-5 transition-colors",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}
