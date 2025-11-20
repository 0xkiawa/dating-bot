# Stage 1: builder
FROM python:3.11-slim-bookworm as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies for Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libc-dev libffi-dev python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN pip install virtualenv
RUN virtualenv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Stage 2: final image
FROM python:3.11-slim-bookworm

WORKDIR /app

# Copy virtual environment
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy project files
COPY . .


# Run migrations and start bot
CMD ["sh", "-c", "alembic upgrade head && python main.py"]