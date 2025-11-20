# Stage 1: builder
FROM python:3.11-slim-bookworm as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libc-dev libffi-dev python3-dev && \
    rm -rf /var/lib/apt/lists/*

RUN pip install virtualenv
RUN virtualenv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install -r requirements.txt


# Stage 2: final
FROM python:3.11-slim-bookworm

USER root
WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy entire project
COPY . .

# Ensure database folder exists
RUN mkdir -p /app/database && chmod -R 777 /app

# Run DB setup ONCE, then start app
CMD ["sh", "-c", "python newdb.py && python main.py"]
