# Streamlit operator UI for the pipeline leak agent, for Amazon ECS Express Mode (Fargate, HTTPS URL).
# Build context is the repo root:  docker build -f agentcore-deploy/ui-ecs-express/Dockerfile -t pipeline-leak-ui .
# The container talks to the AgentCore runtime with the ECS task role; no AWS keys are baked in.
FROM public.ecr.aws/docker/library/python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    AGENT_MODE=agentcore AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1 \
    STREAMLIT_SERVER_PORT=8080 STREAMLIT_SERVER_ADDRESS=0.0.0.0 STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHERUSAGESTATS=false

WORKDIR /app
RUN useradd --system --create-home --shell /usr/sbin/nologin app

COPY requirements.txt ./
RUN pip install -r requirements.txt

# only what the UI needs: the app package and the CSVs the components read
COPY src/ ./src/
COPY data/ ./data/

USER app
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/_stcore/health', timeout=3).read()==b'ok' else 1)"
CMD ["streamlit", "run", "src/app/streamlit_app.py"]
