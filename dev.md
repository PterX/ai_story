# 开发命令备忘

uv run celery -A config worker -l info -P gevent
docker compose exec backend python /app/backend/manage.py createsuperuser


docker build -f docker/Dockerfile . -t ai_story-v2
docker build -f ai_story/docker/frontend.Dockerfile . -t ai_story_frontend-v2

# ai_story 目录下
docker buildx build -f docker/Dockerfile --platform linux/amd64 -t ai_story-v2 . --load

# ai_story-v2 目录下
docker buildx build -f ai_story/docker/frontend.Dockerfile --platform linux/amd64 -t ai_story_frontend-v2 . --load
