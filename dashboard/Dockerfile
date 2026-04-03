FROM oven/bun:latest AS builder

WORKDIR /app
COPY dashboard/package.json ./
RUN bun install

COPY dashboard/ .
RUN bun run prepare && bun run build

FROM nginx:alpine

COPY --from=builder /app/build /usr/share/nginx/html

RUN echo 'server { \
    listen 3000; \
    root /usr/share/nginx/html; \
    index index.html; \
    \
    resolver 127.0.0.11 valid=10s ipv6=off; \
    set $pulse_upstream http://session-pulse:8500; \
    \
    location /api/ { \
        proxy_pass $pulse_upstream; \
        proxy_http_version 1.1; \
        proxy_set_header Upgrade $http_upgrade; \
        proxy_set_header Connection "upgrade"; \
        proxy_set_header Host $host; \
        proxy_read_timeout 86400; \
    } \
    \
    location /healthz { \
        proxy_pass $pulse_upstream; \
    } \
    \
    location /metrics { \
        proxy_pass $pulse_upstream; \
    } \
    \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
    \
    gzip on; \
    gzip_types text/plain text/css application/json application/javascript text/xml; \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
