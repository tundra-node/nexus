FROM node:22-alpine AS builder
WORKDIR /app/client
COPY client/package.json client/pnpm-lock.yaml* ./
RUN corepack enable && pnpm install
COPY client/ .
RUN pnpm run build

FROM nginx:alpine
COPY --from=builder /app/client/dist /usr/share/nginx/html
COPY abyssal-nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
