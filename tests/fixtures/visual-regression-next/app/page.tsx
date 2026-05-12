// Reference page surface used by the Tier 2 integration test. Maps 1:1 to
// the HTML served from server.js — mirrors the Next.js `app/page.tsx`
// convention so the fixture matches the shape the plan calls for, even though
// the test runtime serves the equivalent HTML directly to keep install cost
// bounded.

export default function Page() {
  return (
    <div
      style={{
        width: 200,
        height: 200,
        margin: 50,
        background: '#3b82f6',
        color: '#ffffff',
        font: '24px/200px sans-serif',
        textAlign: 'center',
      }}
    >
      FooButton
    </div>
  );
}
