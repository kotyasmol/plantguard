FROM node:22-alpine AS web-build

WORKDIR /workspace

COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
RUN npm ci --workspace @plantguard/web

COPY apps/web apps/web
RUN npm run build --workspace @plantguard/web

FROM python:3.12-slim

WORKDIR /workspace

COPY services/mining /workspace/services/mining
COPY services/api /workspace/services/api
COPY scripts /workspace/scripts
COPY --from=web-build /workspace/apps/web/dist /workspace/web-dist

RUN python -m pip install --no-cache-dir /workspace/services/mining /workspace/services/api

RUN groupadd --system plantguard \
    && useradd --system --gid plantguard --home-dir /workspace plantguard \
    && mkdir -p /var/lib/plantguard/photos \
    && chown -R plantguard:plantguard /var/lib/plantguard /workspace

ENV PLANTGUARD_WEB_DIST_PATH=/workspace/web-dist

USER plantguard

EXPOSE 8000

CMD ["uvicorn", "plantguard_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
