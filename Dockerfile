FROM node:22-alpine AS web
WORKDIR /web
COPY webapp/package*.json ./
RUN npm ci
COPY webapp/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /srv
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=web /web/dist webapp/dist
WORKDIR /srv/backend
