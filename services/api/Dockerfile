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
COPY --from=web-build /workspace/apps/web/dist /workspace/web-dist

RUN python -m pip install --no-cache-dir /workspace/services/mining /workspace/services/api

ENV PLANTGUARD_WEB_DIST_PATH=/workspace/web-dist

EXPOSE 8000

CMD ["uvicorn", "plantguard_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
