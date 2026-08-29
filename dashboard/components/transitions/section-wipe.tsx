"use client";

import React from "react";
import { motion, AnimatePresence } from "framer-motion";

interface SectionWipeProps {
  children: React.ReactNode;
  activeKey: string;
}

export function SectionWipe({ children, activeKey }: SectionWipeProps) {
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={activeKey}
        initial={{ opacity: 0, y: 8, clipPath: "inset(0 0 100% 0)" }}
        animate={{ opacity: 1, y: 0, clipPath: "inset(0 0 0% 0)" }}
        exit={{ opacity: 0, y: -8, clipPath: "inset(100% 0 0 0)" }}
        transition={{ duration: 0.35, ease: [0.25, 1, 0.5, 1] }}
        className="w-full"
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
