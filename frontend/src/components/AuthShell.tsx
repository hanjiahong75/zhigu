import type { ReactNode } from "react";

interface AuthShellProps {
  overline?: string;
  title: string;
  subtitle?: string;
  children: ReactNode;
}

/**
 * Apple-style glassmorphism authentication shell.
 * Theme-aware via the app's CSS variables / [data-theme] on <html>.
 */
export default function AuthShell({ overline, title, subtitle, children }: AuthShellProps) {
  return (
    <div className="auth-root">
      <div className="auth-blobs" aria-hidden="true">
        <div className="auth-blob auth-blob-1" />
        <div className="auth-blob auth-blob-2" />
        <div className="auth-blob auth-blob-3" />
      </div>

      <div className="auth-content">
        <div className="auth-hero">
          {overline && <div className="auth-overline">{overline}</div>}
          <h1 className="auth-title">{title}</h1>
          {subtitle && <p className="auth-subtitle">{subtitle}</p>}
        </div>

        <div className="auth-card">
          <div className="auth-logo">
            <svg width="26" height="26" viewBox="0 0 28 28" fill="none" aria-hidden="true">
              <defs>
                <linearGradient id="authLogoGrad" x1="0" y1="0" x2="28" y2="28" gradientUnits="userSpaceOnUse">
                  <stop stopColor="#1677ff" />
                  <stop offset="1" stopColor="#7c5cff" />
                </linearGradient>
              </defs>
              <path d="M3 20 L9 12 L14 16 L22 7" stroke="url(#authLogoGrad)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
              <circle cx="22" cy="7" r="2.4" fill="url(#authLogoGrad)" />
            </svg>
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}
