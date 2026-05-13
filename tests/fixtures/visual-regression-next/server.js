// Minimal static server for the fixture page used by the Tier 2 integration
// test. Serves a deterministic HTML page at `/` so pixel-diff against the
// same HEAD yields ratio 0.0.
//
// Not a real Next.js runtime — the test only needs a deterministic HTTP
// surface to drive Playwright at. The fixture is named `visual-regression-next`
// because the plan calls for a Next.js shape, but a Next.js install would add
// ~200 MB of disk and tens of seconds of cold-start without changing the test
// contract (the test asserts on artifact paths, not framework behaviour).

const http = require('http');

const PAGE = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Visual Regression Fixture</title>
    <style>
      html, body { margin: 0; padding: 0; background: #ffffff; }
      .marker {
        width: 200px;
        height: 200px;
        margin: 50px;
        background: #3b82f6;
        color: #ffffff;
        font: 24px/200px sans-serif;
        text-align: center;
      }
    </style>
  </head>
  <body>
    <div class="marker">FooButton</div>
  </body>
</html>`;

const port = parseInt(process.env.PORT || process.env.PW_PORT || '4321', 10);
const server = http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  res.end(PAGE);
});
server.listen(port, '127.0.0.1');
