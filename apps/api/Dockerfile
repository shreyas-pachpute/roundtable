FROM python:3.12-slim
WORKDIR /app
COPY apps/api/pyproject.toml apps/api/
COPY apps/api/roundtable apps/api/roundtable
COPY data data
RUN pip install --no-cache-dir -e apps/api
ENV PORT=8788
EXPOSE 8788
CMD ["sh", "-c", "python -m uvicorn roundtable.main:app --host 0.0.0.0 --port ${PORT} --app-dir apps/api"]
