# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS build
WORKDIR /app
COPY package*.json ./
RUN --mount=type=secret,id=proxy_ca,target=/run/proxy-ca.pem \
    if [ -f /run/proxy-ca.pem ]; then export NODE_EXTRA_CA_CERTS=/run/proxy-ca.pem; fi; npm ci --strict-ssl=true
COPY . .
RUN npm run build
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
