# SessionPulse Dashboard

Real-time observability dashboard for SessionPulse. Built with SvelteKit 2 + Svelte 5.

## Pages

- **Overview** `/` — account grid, pipeline flow, alert banner, summary stats
- **Accounts** `/accounts` — filterable account list by state
- **Account Detail** `/accounts/{phone}` — metrics, timeline, state history
- **Pipeline** `/pipeline` — stage-by-stage health and latency
- **Alerts** `/alerts` — active/resolved alerts with acknowledge
- **Alert Rules** `/alerts/rules` — create, edit, toggle, delete rules

## Development

```bash
bun install
bun run dev        # http://localhost:5173
```

Requires SessionPulse server running at `session-pulse:8500` (proxied via Vite in dev).

## Production Build

```bash
bun run build      # outputs to build/
```

Or via Docker:

```bash
docker compose up session-pulse-dashboard
# Available at http://localhost:5100
```

## Tech Stack

- SvelteKit 2 + Svelte 5 (adapter-static, SPA mode)
- TypeScript strict
- Vanilla CSS (Catppuccin Mocha theme)
- WebSocket for real-time updates
- Nginx for production serving + API proxy

## License

MIT
