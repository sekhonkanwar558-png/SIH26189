# Suishōdama — the officer-facing front end

One chat, and the graph when an answer has a route to show. There is no other screen. The design, and the reasons for it, are README §3.5 and decisions D24–D28; the pivot that produced it is §0.5. **Read those before changing anything here** — the six-section workspace this replaced was deleted on purpose.

It talks only to the frozen HTTP API in root `README.md` §5.6.

## Run from the repository root

```bash
pnpm --dir frontend install
pnpm --dir frontend dev
```

The dev server runs at `http://127.0.0.1:5173` and proxies `/api` to `http://127.0.0.1:8000`, so the backend must be up (`uvicorn backend.api.main:app --port 8000`).

## Checks

```bash
pnpm --dir frontend build
pnpm --dir frontend lint
```

## Layout

```
src/pages/Chat.tsx       the whole product — rail, conversation, composer
src/components/          the graph panel and the evidence trail
src/lib/api.ts           the §5.6 client
src/types.ts             the server's shapes, mirrored — not view models
src/index.css            the palette (D28) and the two animations
```

## Optional environment values

Copy `.env.example` to `.env.local` only when local values need to differ. No secret belongs in a `VITE_` variable, because Vite exposes those values to the browser.
