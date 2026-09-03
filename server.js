const http = require('http');
const { exec } = require('child_process');

const PORT = 3000;

/*
  DEBUG mode: auto-restart the server AND auto-refresh the browser on save.
    - Restart is handled by Node's built-in --watch flag (see package.json
      "dev" script, or run:  DEBUG=true node --watch server.js).
    - Refresh is handled by a tiny Server-Sent-Events channel injected into
      the page below. When you save a file, --watch kills and restarts this
      process; the browser's EventSource connection drops, then reconnects
      to the fresh server and reloads the page.
  Toggle with the DEBUG env var (DEBUG=true) or by passing --debug.
*/
const DEBUG = process.env.DEBUG === 'true' || process.argv.includes('--debug');

// Injected into the page only in DEBUG mode. Reloads on SSE reconnect.
const liveReloadScript = `
<script>
  (function () {
    var dropped = false;
    var es = new EventSource('/__livereload');
    es.addEventListener('open',  function () { if (dropped) location.reload(); });
    es.addEventListener('error', function () { dropped = true; });
  })();
</script>`;

/*
  The graphic is the Lane Lab SVG you uploaded, with two
  changes:
    1. fill swapped from #1155cc → var(--accent) (ivory)
    2. each "notch" rect is given an .lane-notch-{1|2|3} class
       so it can be animated. The notches are then driven by
       three @keyframes (one per lane) that translate them
       left→right along the horizontal portion of the lane,
       then up the curve, with staggered delays per lane.
*/

// The logo SVG, factored out so the gallery can stamp it into each
// panel. Contains no backticks, so the surrounding template literal
// in htmlContent can interpolate it with ${logoSVG} safely.
const logoSVG = `
    <svg class="logo-svg" viewBox="240 140 480 290"
         xmlns="http://www.w3.org/2000/svg">

      <!-- Small upper bars (top right of the logo) -->
      <path d="m548.78 190.76l39.40 0l0 62.58l-39.40 0z"/>
      <path d="m495.32 228.01l39.40 0l0 25.32l-39.40 0z"/>

      <!-- Lane 1: horizontal line + curve + 2 notches -->
      <path d="m317.15 282.70l152.44 0l0 12.44l-152.44 0z"/>
      <path d="m507.78 257.97c-0.81 20.59 -18.10 37.15 -38.80 37.17l0.32 -12.45c13.76 -0.20 25.30 -11.23 26.02 -24.88z"/>
      <path d="m532.37 291.76c0.35 22.77 -20.02 43.10 -47.15 47.07l-1.83 -13.22c20.19 -2.99 35.54 -17.22 35.65 -33.04z"/>
      <path d="m531.14 338.80c-0.89 22.89 -20.19 41.28 -45.86 43.70l-2.03 -12.21c20.04 -1.49 35.08 -15.15 35.56 -32.31z"/>
      <g class="notch-track lane1-n1"><rect class="notch-dot" x="-11" y="-12" width="22" height="24" rx="4"/></g>
      <g class="notch-track lane1-n2"><rect class="notch-dot" x="-11" y="-12" width="22" height="24" rx="4"/></g>

      <!-- Lane 2: horizontal + 2 notches -->
      <path d="m317.36 325.48l167.91 0l0 13.35l-167.91 0z"/>
      <g class="notch-track lane2-n1"><rect class="notch-dot" x="-11" y="-12" width="22" height="24" rx="4"/></g>
      <g class="notch-track lane2-n2"><rect class="notch-dot" x="-11" y="-12" width="22" height="24" rx="4"/></g>

      <!-- Lane 3: horizontal + 2 notches -->
      <path d="m317.36 370.08l167.91 0l0 12.44l-167.91 0z"/>
      <g class="notch-track lane3-n1"><rect class="notch-dot" x="-11" y="-12" width="22" height="24" rx="4"/></g>
      <g class="notch-track lane3-n2"><rect class="notch-dot" x="-11" y="-12" width="22" height="24" rx="4"/></g>

      <!-- Vertical bars (4 ascending, plus the connector) -->
      <path d="m626.13 252.63l15.62 0l0 85.70l-15.62 0z"/>
      <path d="m602.31 159.54l39.40 0l0 93.80l-39.40 0z"/>
      <path d="m518.57 264.48l40.00 0l0 118.14l-40.00 0z"/>
      <path d="m572.35 264.49l40.00 0l0 118.14l-40.00 0z"/>
      <path d="m495.32 252.63l12.44 0l0 5.39l-12.44 0z"/>
    </svg>`;

const htmlContent = `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Lane Lab — Logo Spinner</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;600;700&family=Exo+2:wght@400;500;600&display=swap">
  <style>
    :root {
      --bg:        #142640;
      --panel:     #1d3556;
      --accent:    #fdf9ed;
      --text:      #fdf9ed;
      --text-muted: rgba(253,249,237,0.55);
      --border:    rgba(253,249,237,0.10);
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      min-height: 100vh;
      font-family: "Exo 2", -apple-system, BlinkMacSystemFont, sans-serif;
      color: var(--text);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 40px;
      gap: 28px;
    }
    body::after {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image: radial-gradient(circle at 1px 1px,
        rgba(253,249,237,0.14) 1.2px, transparent 0);
      background-size: 20px 20px;
      z-index: -1;
    }

    .page-title {
      font-family: "Orbitron", sans-serif;
      font-size: 0.95rem;
      text-transform: uppercase;
      letter-spacing: 0.22em;
      color: var(--text-muted);
      text-align: center;
    }

    .hero-card {
      background: color-mix(in srgb, var(--panel) 60%, transparent);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 56px 64px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .logo-svg {
      width: 420px;
      height: auto;
      display: block;
    }

    /* Everything from the source SVG renders in ivory. */
    .logo-svg path, .logo-svg rect { fill: var(--accent); }


    /* ═══ Notch animation ══════════════════════════════════════
       HOW IT WORKS
         Each notch is glued to a CSS motion path (offset-path)
         that traces the CENTRELINE of its lane. The single
         notch-flow keyframe just sweeps offset-distance from
         0%->100%, so the box slides from the start of the path to
         the end. No translate()/rotate() guesswork.

       COORDINATE SPACE
         All path numbers are in SVG user units (the viewBox is
         "240 140 480 290"). A path point of x=288.92 sits exactly
         on a lane because that lane's rect is centred on y=288.92.

       PATH ANATOMY  ── path('M sx sy  H ex')
         M sx sy  start point, on the rail's LEFT edge, so the box
                  fades in on the track (sx = lane rect left edge).
         H ex     draw a horizontal line to x=ex (end of the lane's
                  straight section). The box travels along this.

       LANE CENTRELINES (y), START x and END x:
         lane 1:  y = 288.92   start x = 317.15   end x = 469.59
         lane 2:  y = 332.16   start x = 317.36   end x = 485.27
         lane 3:  y = 376.30   start x = 317.36   end x = 485.27
       (y = rect top + height/2;  start x = rect left;  end x = left + width)
     ────────────────────────────────────────────────────────── */
    /* Motion and scale are on SEPARATE elements so they never share a
       transform stack. offset-path on the <g> moves its local-space origin
       along the lane; scale on the <rect> inside collapses it to that same
       origin — no composition ambiguity, no fly-away. */
    .notch-track {
      transform-box: fill-box;
      offset-anchor: center;
      offset-rotate: auto;
      animation: notch-move var(--duration, 3.6s) linear infinite backwards;
      animation-delay: var(--delay, 0s);
    }
    .notch-dot {
      transform-box: fill-box;
      animation: notch-scale var(--duration, 3.6s) linear infinite backwards;
      animation-delay: var(--delay, 0s);
    }

    /* One centreline path per lane: straight section + the bend up into
       the bars. Each path starts at the rail's LEFT edge, so boxes fade
       in on the track rather than out in empty space to its left. The
       C bezier traces the elliptical bend (derivation note below). */
    .lane1-n1, .lane1-n2 { offset-path: path('M 317.15 288.92 H 469.14 C 486.37 288.81 500.79 275.01 501.55 257.89 L 501.55 228'); }
    .lane2-n1, .lane2-n2 { offset-path: path('M 317.36 332.16 H 484.31 C 507.97 328.74 525.83 311.46 525.71 292.17'); }
    .lane3-n1, .lane3-n2 { offset-path: path('M 317.36 376.30 H 484.27 C 507.12 374.44 524.29 358.42 524.98 338.39'); }

    /* Two boxes per lane. The *-n2 delay sets the gap between the
       pair (bigger delay = box trails further behind its partner).
       The small per-lane offsets stagger the three lanes.       */
    /* All lanes share the same 3.6s cycle so the stagger between lanes stays
       constant and never drifts. n2 delay = n1 + 1.8s (half-cycle gap).
       Both --delay and --duration inherit to the child .notch-dot. */
    .lane1-n1, .lane1-n2,
    .lane2-n1, .lane2-n2,
    .lane3-n1, .lane3-n2 { --duration: 4.3s; }

    .lane1-n1 { --delay: 0s;    }
    .lane1-n2 { --delay: 2.15s; }
    .lane2-n1 { --delay: 0.4s;  }
    .lane2-n2 { --delay: 2.55s; }
    .lane3-n1 { --delay: 0.8s;  }
    .lane3-n2 { --delay: 2.95s; }

    /* notch-move: the <g> drifts along the lane path. Pure motion, no scale.
       notch-scale: the <rect> inside grows then shrinks. Pure scale, no motion.
       Because they live on different elements, CSS never has to compose
       offset-path + scale on the same transform stack — the source of the
       fly-away bug. scale:0 collapses the rect to the <g>'s local origin,
       which is always exactly the current path point. KNOBs below. */
    @keyframes notch-move {
      0%   { offset-distance: 0%; }
      100% { offset-distance: 100%; }
    }
    @keyframes notch-scale {
      0%   { scale: 0; }   /* zero-size at the track start                    */
      10%  { scale: 1; }   /* grown to full size, on the track                */
      85%  { scale: 1; }   /* KNOB: shrink starts here (farther back)         */
      97%  { scale: 0; }   /* KNOB: fully shrunk (20% window = slower shrink) */
      100% { scale: 0; }   /* held at zero; loop reset is invisible           */
    }
    /* Lane 1 curves upward into the bar — stays full-size through the bend,
       then collapses more gradually as it enters the bar face. */
    @keyframes notch-scale-lane1 {
      0%   { scale: 0; }
      10%  { scale: 1; }
      84%  { scale: 1; }   /* KNOB: start of shrink (matches lanes 2&3 timing) */
      100% { scale: 0; }   /* collapses inside the bar                              */
    }
    .lane1-n1 .notch-dot, .lane1-n2 .notch-dot {
      animation-name: notch-scale-lane1;
    }

    /* ═══ The bend up into the bars (DONE) ═════════════════════
       Each offset-path above = straight H line + a cubic Bezier C
       curve through the bend. The bends in the artwork are arcs of
       ellipses, not circles, so a circular A arc can't trace them.

       The exact centreline was derived from the crescent shapes that
       draw each bend in the SVG below (the three paths just before
       the notch rects). A crescent has an OUTER edge and an INNER
       edge, both cubic Beziers. The track centreline is their
       point-by-point average: reverse the inner edge so both run the
       same direction, then average the endpoints + control points.
       That average is itself a cubic Bezier — the C curve used above.

       offset-rotate:auto turns the box through the curve, so nothing
       else is needed. To retrace after editing the artwork, re-average
       the matching crescent's two edges.
     ────────────────────────────────────────────────────────── */
  </style>
</head>
<body>
  <div class="page-title">Lane Lab — animated logo</div>

  <div class="hero-card">
    ${logoSVG}
  </div>
</body>
</html>
`;

const server = http.createServer((req, res) => {
  // Live-reload channel (DEBUG only): held open; drops when the server
  // restarts, prompting the browser to reconnect + reload.
  if (DEBUG && req.url === '/__livereload') {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    });
    res.write('retry: 500\n\n');                    // reconnect 500ms after a drop
    const ping = setInterval(() => res.write(': ping\n\n'), 10000);
    req.on('close', () => clearInterval(ping));
    return;
  }

  const body = DEBUG
    ? htmlContent.replace('</body>', `${liveReloadScript}\n</body>`)
    : htmlContent;
  res.writeHead(200, { 'Content-Type': 'text/html' });
  res.end(body);
});

server.listen(PORT, () => {
  const url = `http://localhost:${PORT}`;
  console.log(`\x1b[32m✔\x1b[0m Logo spinner preview at: ${url}${DEBUG ? '  \x1b[33m(DEBUG: live-reload on)\x1b[0m' : ''}`);
  // In DEBUG/watch mode the page reloads itself, so don't spawn a new browser
  // tab on every restart — open it once yourself. Otherwise auto-open.
  if (!DEBUG) {
    const startCmd = process.platform === 'darwin' ? 'open' : process.platform === 'win32' ? 'start' : 'xdg-open';
    exec(`${startCmd} ${url}`);
  }
});
