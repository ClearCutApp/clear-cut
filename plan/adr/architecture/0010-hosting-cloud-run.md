# ADR 0010: Host on Cloud Run

Status: Accepted
Date: 2026-08-29

## Context

The legacy docs pin Replit for hosting and the frontend. The submission needs a
hosted URL, and the runtime already lives on Google Cloud.

## Decision

One Cloud Run service serves the JSON API and the static web/ build from the
same container. The Vite output gets baked into the image at build time, and
gcloud run deploy ships it. Replit is dropped; a second platform adds a deploy
target, a secrets store, and a failure mode without adding capability.

## Consequences

We forgo Replit's hackathon credits. Same-origin serving removes CORS
configuration entirely. Every frontend change now requires an image rebuild
and a redeploy, which is slower than Replit's push-to-run loop.
