FROM node:20-alpine AS builder
WORKDIR /app

# Copy workspace manifests so npm can resolve all workspaces
COPY package.json package-lock.json ./
COPY packages/shared-services/package.json ./packages/shared-services/
COPY apps/web/package.json ./apps/web/
COPY apps/mobile/package.json ./apps/mobile/

RUN npm install

# Copy shared package source (may be imported by root app)
COPY packages/shared-services/ ./packages/shared-services/

# Copy root app source
COPY src/ ./src/
COPY index.html vite.config.ts postcss.config.mjs ./

ARG VITE_API_URL=http://localhost:6969/api
ENV VITE_API_URL=$VITE_API_URL

RUN npx vite build

FROM nginx:alpine AS runner
COPY --from=builder /app/dist /usr/share/nginx/html
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf

RUN addgroup -S appgroup && adduser -S appuser -G appgroup \
    && mkdir -p /var/cache/nginx/client_temp \
                /var/cache/nginx/proxy_temp \
                /var/cache/nginx/fastcgi_temp \
                /var/cache/nginx/uwsgi_temp \
                /var/cache/nginx/scgi_temp \
    && chown -R appuser:appgroup /var/cache/nginx /etc/nginx/conf.d \
    && sed -i 's|pid\s*/[^;]*\.pid;|pid /tmp/nginx.pid;|' /etc/nginx/nginx.conf

USER appuser
EXPOSE 3010
CMD ["nginx", "-g", "daemon off;"]
