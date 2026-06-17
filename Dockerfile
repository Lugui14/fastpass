# ==============================================================================
# Stage 1: Build dependencies using uv
# ==============================================================================
FROM python:3.8-slim-bookworm AS builder

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies needed for building packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy uv binary from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency definitions
COPY pyproject.toml uv.lock ./

# Sync dependencies to .venv (excluding development dependencies)
RUN uv sync --frozen --no-cache --no-dev


# ==============================================================================
# Stage 2: Final minimal production runner
# ==============================================================================
FROM python:3.8-slim-bookworm AS runner

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Create a non-root group and user for security
RUN groupadd -r django && useradd -r -g django -d /app django

# Copy the virtual environment from the builder
COPY --from=builder /app/.venv /app/.venv

# Copy project files
COPY . .

# Make the entrypoint executable and set folder ownership to the non-root user
RUN chmod +x entrypoint.sh && chown -R django:django /app

# Switch to the non-root user
USER django

# Expose the application port
EXPOSE 8000

# Set entrypoint and default command using Gunicorn
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "fastpass.wsgi:application"]
