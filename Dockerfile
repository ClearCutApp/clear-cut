# One image serving the JSON API and the SPA from the same origin (ADR 0010),
# which is what removes CORS configuration from the project entirely.
#
# Two stages because the Vite build needs node and the runtime does not. The
# SPA is built here rather than copied from the host: .gitignore excludes
# web/dist, so gcloud's generated .gcloudignore excludes it too, and an image
# expecting it from the build context would ship without it and serve the
# missing-build response on every page.

# ---------------------------------------------------------------- web build --
FROM node:22-slim AS web

WORKDIR /build/web

# package.json and the lockfile first: this layer is cached until a dependency
# actually changes, so an edit to src/ does not reinstall node_modules.
COPY web/package.json web/package-lock.json* ./
RUN npm ci

COPY web/ ./
RUN npm run build

# ------------------------------------------------------------------ runtime --
FROM python:3.12-slim AS runtime

# PYTHONDONTWRITEBYTECODE: the filesystem is ephemeral, so .pyc files are dead
# weight. PYTHONUNBUFFERED: Cloud Run reads stdout, and a buffered stream loses
# the last log lines of a crashing revision, which are the ones worth having.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies before source, for the same layer-cache reason as above.
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

COPY main.py ./
COPY --from=web /build/web/dist ./web/dist

# Non-root: nothing here needs to write to the image, and a compromised
# process should not be able to.
RUN useradd --create-home --uid 1001 clearcut
USER clearcut

# Cloud Run injects PORT and routes to it on every interface. main.py's own
# __main__ block binds 127.0.0.1, which is right for local development and
# unreachable in a container -- the revision would look healthy and answer
# nothing. Shell form so $PORT expands; gunicorn rather than Flask's
# development server, which is single-threaded and states plainly that it is
# not for production use.
ENV PORT=8080
EXPOSE 8080
CMD exec gunicorn --bind "0.0.0.0:$PORT" --workers 1 --threads 8 --timeout 0 main:app
