# Stage 1: Build
FROM node:22-alpine AS builder

WORKDIR /app

# Build context must be ./frontend (contains client/ and shared/)
COPY client/package.json client/pnpm-workspace.yaml ./client/
COPY client/ ./client/
COPY shared/ ./shared/

RUN corepack enable && \
    cd client && \
    pnpm install && \
    npx vite build

# Stage 2: Serve
FROM nginx:alpine

COPY --from=builder /app/client/dist /usr/share/nginx/html
COPY client/frontend-nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
