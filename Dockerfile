FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .

EXPOSE 8080

# Mount AWS credentials via env vars or volume mount of ~/.aws
# docker run -p 8080:8080 -v ~/.aws:/root/.aws ops-agent-dashboard
# or: docker run -p 8080:8080 -e AWS_ACCESS_KEY_ID=... -e AWS_SECRET_ACCESS_KEY=... ops-agent-dashboard

CMD ["python", "-m", "ops_agent.cli", "dashboard", "--host", "0.0.0.0", "--port", "8080"]
