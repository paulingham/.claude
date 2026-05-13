// Minimal Next.js config — present so consumers that inspect the fixture for
// Next.js shape find what they expect. The integration test uses server.js
// rather than `next dev` to avoid a multi-minute first-build cost; this file
// is the static reference for what the build pipeline would look like.

module.exports = { reactStrictMode: true };
