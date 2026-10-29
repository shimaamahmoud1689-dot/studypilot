FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend backend
COPY frontend frontend
ENV PORT=8080 TRUST_PROXY=1
EXPOSE 8080
# One worker on purpose: uploaded lectures are kept in memory, so all requests must reach the same process.
CMD ["sh", "-c", "cd backend && gunicorn app:app --workers 1 --threads 4 --timeout 600 --bind 0.0.0.0:${PORT}"]
