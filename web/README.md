# regrag-web

Next.js 15 (App Router) + Tailwind v4 frontend for the regrag backend.

## Run independently

```bash
pnpm install
cp .env.local.example .env.local      # NEXT_PUBLIC_API_URL=http://localhost:8000
pnpm dev                              # http://localhost:3000
```

The frontend assumes the FastAPI backend is reachable at
`NEXT_PUBLIC_API_URL`. If you don't have it running you'll see the
"Backend unreachable" error state, which is the expected behaviour.

## Pages

| route        | what it does                                                                |
| ------------ | --------------------------------------------------------------------------- |
| `/`          | Main Q&A — full RAG pipeline (retrieve → rerank → generate → cite)          |
| `/search`    | Retrieval debug view — runs hybrid + rerank but skips the LLM               |
| `/documents` | Catalogue of every ingested PDF with a short preview, regulator / search filters |
| `/about`     | Project overview, architecture diagram, corpus stats, eval results          |

## Design choices

- **Tailwind v4** with CSS-driven theming (`@theme`) — no JS config file.
- **shadcn-style primitives** are inlined under `components/ui/` so we don't
  depend on a CLI step. They use Radix primitives + CVA for variants.
- **Zod validates every API response.** If the backend ever drifts, the
  parse fails loudly rather than corrupting the UI silently.
- **TanStack Query** for the /ask + /search mutations. No global store.
- **Server components** for `/about` so the corpus stats and eval table
  are read from the repo on the server at build time and never ship to
  the client.

## Scripts

```bash
pnpm dev         # dev server
pnpm build       # production build (set NEXT_OUTPUT_STANDALONE=true for Docker)
pnpm start       # serve the build
pnpm lint        # ESLint
pnpm typecheck   # tsc --noEmit
```

## Notes on Windows

`output: "standalone"` in `next.config.ts` is gated behind
`NEXT_OUTPUT_STANDALONE=true` because OneDrive on Windows blocks the
symlinks Next.js creates during the trace step. The Docker image (Linux)
sets that env var; local development on Windows skips it.
