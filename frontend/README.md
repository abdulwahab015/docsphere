# DocSphere frontend

React + TypeScript single-page app for the DocSphere API, built with Vite.

## Stack

- **React 19**, **TypeScript** (strict), **Vite**
- **React Router** for routing, **TanStack Query** for server state, **axios** for HTTP
- **React Hook Form** + **Zod** for forms and validation
- **Tailwind CSS v4** + **shadcn/ui** (Radix) for styling and components
- **Vitest** + **Testing Library** + **MSW** for tests
- **oxlint** for linting, **Prettier** for formatting

## Getting started

Requires Node 22 (see `.nvmrc`). Run these from the repository root:

```sh
cp frontend/.env.example frontend/.env   # once; points the app at the local API
make fe-install                          # npm ci
make fe-dev                              # http://localhost:3000
```

Run the backend on `http://localhost:8000` alongside it (`make run`). Open the app on
`localhost`, not `127.0.0.1`: the refresh-token cookie is only shared between the app and the
API when both are on the same site.

The dev server must run on port 3000. The backend's `FRONTEND_URL` and
`CORS_ALLOWED_ORIGINS` default to `http://localhost:3000`, and so do the links it
puts in emails.

## Commands

| Make target         | What it does                                           |
| ------------------- | ------------------------------------------------------ |
| `make fe-dev`       | Dev server with hot reload                             |
| `make fe-test`      | Run the test suite                                     |
| `make fe-test-cov`  | Run tests under coverage (fails below 95%)             |
| `make fe-lint`      | oxlint                                                 |
| `make fe-format`    | Prettier `--write`                                     |
| `make fe-check`     | Full CI sequence: format, lint, types, coverage, build |
| `make fe-build`     | Production build into `frontend/dist/`                 |
| `make fe-api-types` | Regenerate `src/api/schema.d.ts` from the Django API   |
| `make fe-e2e`       | Playwright end-to-end tests against the real API       |

## End-to-end tests

`make fe-e2e` (backend venv active) runs Playwright in a real browser against the whole
stack. It starts its own servers, so it never touches your dev database or dev servers:

- **API on :8001:** a fresh SQLite database, migrated and seeded from `e2e/seed.json` by
  `manage.py seed_e2e`.
- **App on :3100:** the production build (`vite build` + `vite preview`).

The test accounts live in `e2e/seed.json`, and `e2e/fixtures.ts` reads the same file. Add
accounts there, not in the tests. The first run needs a browser:
`cd frontend && npx playwright install chromium`. When a test fails, a screenshot and trace
are written to `frontend/test-results/`. Open a trace with `npx playwright show-trace <zip>`.

## API types

`src/api/schema.d.ts` is generated from the backend's OpenAPI schema. Never edit
it by hand. After changing a backend serializer or endpoint, run
`make fe-api-types` (with the backend venv active) and commit the result together
with the backend change.

## Project layout

```text
e2e/              # Playwright specs, fixtures.ts, seed.json (also loaded by manage.py seed_e2e)
src/
├── api/          # HTTP client (token refresh), error parsing, generated schema.d.ts + type aliases
├── app/          # App root, route table, paths, sidebar navigation, layouts (shell, sidebar, menus)
├── components/   # Shared components (page header, states, dialogs, badges, form/); ui/ = shadcn
├── features/     # One folder per domain: auth, people, organization, projects, documents, sharing
├── hooks/        # Shared hooks (URL list params, page title, id params)
├── lib/          # Framework-agnostic helpers (env, access rules, formatting, form errors)
├── pages/        # Route-level pages that belong to no single feature (not found, error)
└── test/         # Test setup, MSW server, render helper, factories
```

Add shadcn components with `npx shadcn@latest add <name>` from `frontend/`.
