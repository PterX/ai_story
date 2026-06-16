FROM node:22-alpine AS linknow-build

WORKDIR /build/linknow/tapnow-studio

COPY linknow/tapnow-studio/package*.json ./
RUN npm ci

COPY linknow/tapnow-studio/ ./

ARG LINKNOW_API_BASE_URL=
ARG LINKNOW_CACHE_SERVER_URL=
ARG LINKNOW_TRANSFER_STATION_URL=
ENV VITE_AI_API_BASE_URL=${LINKNOW_API_BASE_URL} \
    VITE_CACHE_SERVER_URL=${LINKNOW_CACHE_SERVER_URL} \
    VITE_TRANSFER_STATION_URL=${LINKNOW_TRANSFER_STATION_URL}

RUN npm run build

FROM node:22-alpine AS admin-build

WORKDIR /build/ai_story/frontend

COPY ai_story/frontend/package*.json ./
RUN npm ci

COPY ai_story/frontend/ ./

ARG ADMIN_BASE_PATH=/admin/
ARG ADMIN_API_BASE_URL=/api/v1
ARG ADMIN_SSE_BASE_URL=
ENV APP_BASE_PATH=${ADMIN_BASE_PATH} \
    VUE_APP_API_BASE_URL=${ADMIN_API_BASE_URL} \
    VUE_APP_SSE_BASE_URL=${ADMIN_SSE_BASE_URL}

RUN npm run build

FROM nginx:1.25-alpine

COPY ai_story/docker/nginx/frontend.conf /etc/nginx/conf.d/default.conf
COPY --from=linknow-build /build/linknow/tapnow-studio/dist /usr/share/nginx/html
COPY --from=admin-build /build/ai_story/dist /usr/share/nginx/html/admin

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
