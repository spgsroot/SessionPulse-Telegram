FROM python:3.11-slim AS builder

WORKDIR /build

# Install SDK from local source
COPY sdk /tmp/sdk
RUN pip install --no-cache-dir /tmp/sdk[kafka]

COPY server/pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /install /usr/local
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY server/server/ ./server/
COPY server/config/ ./config/

RUN useradd -r -u 1001 pulse
USER pulse

EXPOSE 8500

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8500", "--workers", "1"]
