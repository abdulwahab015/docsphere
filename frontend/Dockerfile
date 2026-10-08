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
# The git commit a release is built from, which error reports name.
ARG RELEASE=""
RUN VITE_API_BASE_URL="$VITE_API_BASE_URL" \
    VITE_SENTRY_RELEASE="$RELEASE" \
    npm run build


# Runs as an unprivileged user, so it listens on 8080 rather than 80.
FROM nginxinc/nginx-unprivileged:1.31-alpine

# Templates, filled in at start-up from the container's environment
# (${DJANGO_ADMIN_PATH}, the SENTRY_* settings) into /etc/nginx/conf.d/, so
# one image serves every environment.
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY nginx/app-headers.inc.template /etc/nginx/templates/app-headers.inc.template
# Defined even when unset, or the templates would keep the placeholders
# themselves. Error reporting stays off without a DSN.
ENV SENTRY_FRONTEND_DSN="" \
    SENTRY_ENVIRONMENT="production" \
    SENTRY_INGEST_ORIGIN=""
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
