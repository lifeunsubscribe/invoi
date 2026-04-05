/**
 * Simple tooltip component for UI hints
 *
 * Wraps children with a hover/focus tooltip to guide new users.
 */

import { useState } from "react";

export default function Tooltip({ children, text, position = "top" }) {
  const [visible, setVisible] = useState(false);

  const tooltipStyle = {
    position: "absolute",
    background: "#2c1810",
    color: "white",
    padding: "8px 12px",
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 500,
    whiteSpace: "nowrap",
    zIndex: 1000,
    pointerEvents: "none",
    boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
    opacity: visible ? 1 : 0,
    transition: "opacity 0.2s",
    // Position based on prop
    ...(position === "top" && {
      bottom: "calc(100% + 8px)",
      left: "50%",
      transform: "translateX(-50%)",
    }),
    ...(position === "bottom" && {
      top: "calc(100% + 8px)",
      left: "50%",
      transform: "translateX(-50%)",
    }),
    ...(position === "left" && {
      right: "calc(100% + 8px)",
      top: "50%",
      transform: "translateY(-50%)",
    }),
    ...(position === "right" && {
      left: "calc(100% + 8px)",
      top: "50%",
      transform: "translateY(-50%)",
    }),
  };

  // Small arrow pointer
  const arrowStyle = {
    position: "absolute",
    width: 0,
    height: 0,
    borderStyle: "solid",
    ...(position === "top" && {
      top: "100%",
      left: "50%",
      transform: "translateX(-50%)",
      borderWidth: "6px 6px 0 6px",
      borderColor: "#2c1810 transparent transparent transparent",
    }),
    ...(position === "bottom" && {
      bottom: "100%",
      left: "50%",
      transform: "translateX(-50%)",
      borderWidth: "0 6px 6px 6px",
      borderColor: "transparent transparent #2c1810 transparent",
    }),
    ...(position === "left" && {
      left: "100%",
      top: "50%",
      transform: "translateY(-50%)",
      borderWidth: "6px 0 6px 6px",
      borderColor: "transparent transparent transparent #2c1810",
    }),
    ...(position === "right" && {
      right: "100%",
      top: "50%",
      transform: "translateY(-50%)",
      borderWidth: "6px 6px 6px 0",
      borderColor: "transparent #2c1810 transparent transparent",
    }),
  };

  return (
    <div
      style={{ position: "relative", display: "inline-block" }}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      {children}
      {text && (
        <div style={tooltipStyle}>
          {text}
          <div style={arrowStyle} />
        </div>
      )}
    </div>
  );
}
