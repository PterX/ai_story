# Docker 镜像打包流程

这个流程将两个前端打进同一个 nginx 静态镜像：

- `linknow/tapnow-studio` 通过 Vite 构建后挂载到 `/`
- `ai_story/frontend` 通过 Webpack 构建后挂载到 `/admin`
- `/api/` 由 nginx 反向代理到 Django 后端 `backend:8010`
- 后端服务与 Celery Worker 继续沿用 `ai_story/docker/Dockerfile`

## 本地构建与启动

从 `ai_story/` 目录执行：

```bash
docker compose build
docker compose up -d
```

访问入口：

- linknow: `http://localhost:3000/`
- ai_story 管理前端: `http://localhost:3000/admin/`
- Django API: `http://localhost:3000/api/v1/`

## 单独构建镜像

后端镜像：

```bash
cd ai_story
docker build -f docker/Dockerfile -t xhongc/ai_story-backend .
```

统一前端镜像需要从仓库根目录构建，因为它同时读取 `ai_story/frontend` 和 `linknow/tapnow-studio`：

```bash
docker build -f ai_story/docker/frontend.Dockerfile -t xhongc/ai_story-frontend .
```

如需覆盖前端请求的 API 地址：

```bash
docker build \
  -f ai_story/docker/frontend.Dockerfile \
  --build-arg LINKNOW_API_BASE_URL= \
  --build-arg LINKNOW_TRANSFER_STATION_URL=https://example.com/transfer \
  --build-arg ADMIN_BASE_PATH=/admin/ \
  --build-arg ADMIN_API_BASE_URL=/api/v1 \
  -t xhongc/ai_story-frontend .
```

## 部署

`docker-compose-deploy.yml` 继续使用两个镜像：

- `xhongc/ai_story-backend`: Django 后端和 Celery Worker 共用
- `xhongc/ai_story-frontend`: nginx 静态入口，提供 `/` 和 `/admin`

Celery Worker 保持在 `/app/backend` 启动：

```yaml
working_dir: /app/backend
command: celery -A config worker -l info -P gevent
```
