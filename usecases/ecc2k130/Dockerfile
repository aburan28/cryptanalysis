FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --requirement requirements.txt \
    && useradd --create-home --uid 10001 cryptanalysis

COPY handler.py publish_api.py reconcile.py service.py stream.py ./
USER 10001:10001

CMD ["python", "service.py"]
