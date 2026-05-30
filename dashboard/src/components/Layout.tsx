import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

const NAV = [
  { to: "/", label: "Overview", end: true },
  { to: "/traces", label: "Traces", end: false },
  { to: "/alerts", label: "Alerts", end: false },
  { to: "/prompts", label: "Prompts", end: false },
];

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="dot" />
          Sentinel
        </div>
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
          >
            {item.label}
          </NavLink>
        ))}
        <div style={{ marginTop: "auto", color: "var(--muted)", fontSize: 12 }}>
          v0.1.1 · self-hosted
        </div>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}
