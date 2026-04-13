FROM python:3.11-alpine

RUN apk add --no-cache gcc musl-dev libffi-dev

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

ENV DATA_DIR=/app/data
ENV RUSTDESK_DB=/rustdesk-data/db_v2.sqlite3
ENV FLASK_DEBUG=0

EXPOSE 21114

CMD ["gunicorn", "--bind", "0.0.0.0:21114", "--workers", "2", "--timeout", "120", "app:app"]
