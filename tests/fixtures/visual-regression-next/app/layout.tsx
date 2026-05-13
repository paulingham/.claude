// Root layout — mirrors the Next.js app-router convention required by the
// plan's "fixture Next.js project" wording. The runtime path renders via
// server.js (see fixture README); this file documents the intended Next.js
// shape so a future build runtime can serve from the same surface.

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, padding: 0, background: '#ffffff' }}>
        {children}
      </body>
    </html>
  );
}
