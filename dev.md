# 开发命令备忘

uv run celery -A config worker -l info -P gevent


docker build -f docker/Dockerfile . -t ai_story-v2
docker build -f docker/frontend.Dockerfile . -t ai_story_frontend-v2
