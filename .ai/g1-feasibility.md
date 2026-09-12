# G1 Feasibility

## Approved Defaults

- New repository only: `zhilian-echomind`.
- Original EchoMind is reference material only.
- Local demo first.
- Frontend: Vite + Vue.
- Backend: FastAPI.
- Model provider: mock mode first, OpenAI official API can be added after the local loop is stable.
- Demo data: synthetic and de-identified only.

## Smallest Proof

- Python 3.12.4 is available.
- Node v24.13.0 and npm 11.6.2 are available.
- FastAPI is not installed in the global environment, so the backend includes `apps/api/requirements.txt`.
- Core backend behavior is testable without starting a server.
- Vite production build succeeds when minification is disabled. The default minifier exits without a useful JS error in this Windows path, so demo builds use `vite build --minify false`.

## Architecture Decision

ADR-001: Use a local-first monorepo with `apps/api` and `apps/web`.

Reason:

- Keeps the original EchoMind untouched.
- Lets the demo run without external services.
- Allows later replacement of mock provider with OpenAI official API.
- Makes token usage predictable because the long content sits in local storage and each request uses small retrieved chunks.
