# CaseLens frontend

The officer-facing React application for SIH26189. It uses the frozen HTTP API documented in the repository root `README.md`.

## Run from the repository root

```bash
pnpm --dir frontend install
pnpm --dir frontend dev
```

The development server runs at `http://127.0.0.1:5173` and proxies `/api` to `http://127.0.0.1:8000`.

## Checks

```bash
pnpm --dir frontend build
pnpm --dir frontend lint
```

## Optional environment values

Copy `.env.example` to `.env.local` only when local values need to differ. No secret belongs in a `VITE_` variable because Vite exposes those values to the browser.
