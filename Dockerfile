# ########################################
# ETAPA 1: BUILDER (Compilación y dependencias con uv)
# ########################################
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=0 \
    UV_LINK_MODE=copy

WORKDIR /app

# 1. Copiamos solo los manifiestos para maximizar la caché de capas de Docker
COPY pyproject.toml uv.lock ./

# 2. Instalamos solo las dependencias de producción en el .venv
RUN uv sync --frozen --no-dev --no-install-project

# 3. Copiamos el código fuente e instalamos el paquete actual
COPY README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

# 4. Limpieza de bytecode y tests internos de librerías para reducir peso
RUN find /app/.venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true

# ########################################
# ETAPA 2: RUNNER (Imagen final ligera y segura)
# ########################################
FROM python:3.12-slim-bookworm AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# 1. Instalamos dependencias nativas del sistema requeridas por WeasyPrint
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libffi8 \
    libgdk-pixbuf-2.0-0 \
    libglib2.0-0 \
    libharfbuzz0b \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    shared-mime-info \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# 2. Creamos un usuario no-root seguro con UID/GID explícito sin shell interactivo
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -s /sbin/nologin -M appuser

# 3. Copiamos la aplicación instalada y el entorno virtual desde el builder
COPY --from=builder --chown=appuser:appuser /app /app

# 4. Cambiamos al usuario no privilegiado
USER appuser

EXPOSE 8000

# 5. Healthcheck nativo en Python (sin dependencias adicionales)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

# 6. Ejecución del servidor FastAPI
CMD ["uvicorn", "pactus_backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
