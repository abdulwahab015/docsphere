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
RUN VITE_API_BASE_URL="$VITE_API_BASE_URL" npm run build


# Runs as an unprivileged user, so it listens on 8080 rather than 80.
FROM nginxinc/nginx-unprivileged:1.27-alpine

# Read at start-up: ${DJANGO_ADMIN_PATH} in the template is filled in from the
# container's environment.
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY nginx/app-headers.conf /etc/nginx/snippets/app-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
