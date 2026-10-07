# The production frontend: builds the single-page app, then serves it with
# nginx, which also forwards Django's paths to the `web` service - so the
# browser sees one origin for the app and the API.
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# Empty: the app calls the API on its own origin (/api/v1), through nginx.
ARG VITE_API_BASE_URL=""
# Error reporting from the browser; off while the DSN is empty.
ARG VITE_SENTRY_DSN=""
ARG VITE_SENTRY_ENVIRONMENT="production"
ARG VITE_SENTRY_RELEASE=""
RUN VITE_API_BASE_URL="$VITE_API_BASE_URL" \
    VITE_SENTRY_DSN="$VITE_SENTRY_DSN" \
    VITE_SENTRY_ENVIRONMENT="$VITE_SENTRY_ENVIRONMENT" \
    VITE_SENTRY_RELEASE="$VITE_SENTRY_RELEASE" \
    npm run build


# Runs as an unprivileged user, so it listens on 8080 rather than 80.
FROM nginxinc/nginx-unprivileged:1.27-alpine

# Templates, filled in at start-up from the container's environment
# (${DJANGO_ADMIN_PATH}, ${SENTRY_INGEST_ORIGIN}) into /etc/nginx/conf.d/.
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY nginx/app-headers.inc.template /etc/nginx/templates/app-headers.inc.template
# Defined even when unset, or the template would keep the placeholder itself.
ENV SENTRY_INGEST_ORIGIN=""
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
