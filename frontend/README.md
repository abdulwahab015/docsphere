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
make fe-install   # npm ci
make fe-dev       # http://localhost:3000
```

The dev server must run on port 3000. The backend's `FRONTEND_URL` and
`CORS_ALLOWED_ORIGINS` default to `http://localhost:3000`, and so do the links it
puts in emails.

## Commands

| Make target         | What it does                                           |
| ------------------- | ------------------------------------------------------ |
| `make fe-dev`       | Dev server with hot reload                             |
| `make fe-test`      | Run the test suite                                     |
| `make fe-test-cov`  | Run tests under coverage (fails below 90%)             |
| `make fe-lint`      | oxlint                                                 |
| `make fe-format`    | Prettier `--write`                                     |
| `make fe-check`     | Full CI sequence: format, lint, types, coverage, build |
| `make fe-build`     | Production build into `frontend/dist/`                 |
| `make fe-api-types` | Regenerate `src/api/schema.d.ts` from the Django API   |

## API types

`src/api/schema.d.ts` is generated from the backend's OpenAPI schema. Never edit
it by hand. After changing a backend serializer or endpoint, run
`make fe-api-types` (with the backend venv active) and commit the result together
with the backend change.

## Project layout

```text
src/
├── api/          # schema.d.ts (generated) and, later, the HTTP client
├── app/          # App root, providers, route table, route paths
├── components/   # Shared components; ui/ holds shadcn-generated primitives
├── features/     # One folder per domain (auth, projects, documents, ...)
├── lib/          # Small framework-agnostic helpers
├── pages/        # Route-level pages that don't belong to a single feature
└── test/         # Test setup and shared test utilities
```

Add shadcn components with `npx shadcn@latest add <name>` from `frontend/`.
