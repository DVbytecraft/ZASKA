FROM node:20-alpine AS builder

WORKDIR /app

# Shared package (resolved via file:../../packages/shared-services)
COPY packages/shared-services /packages/shared-services

# Web app
COPY apps/web/package.json ./package.json
RUN npm install
COPY apps/web .
RUN npm run build

FROM nginx:alpine AS runner
COPY --from=builder /app/dist /usr/share/nginx/html
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf

RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

EXPOSE 3010
CMD ["nginx", "-g", "daemon off;"]
