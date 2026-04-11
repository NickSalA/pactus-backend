# ########################################
# ETAPA 1: BUILDER
# ########################################
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1. Creamos el entorno virtual directamente (¡Ya no necesitamos apt-get!)
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 2. Copiamos SOLO los requerimientos para aprovechar la caché
COPY requirements.txt .

# 3. Instalamos dependencias. Las wheels de asyncpg/psycopg3 se instalarán rapidísimo
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ########################################
# ETAPA 2: RUNNER (Final)
# ########################################
FROM python:3.12-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# 1. Creamos el usuario no-root (Seguridad)
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 2. Traemos el entorno virtual listo desde el builder
COPY --from=builder /opt/venv /opt/venv

# 3. Copiamos el código de la app con los permisos correctos
COPY --chown=appuser:appuser . .

# 4. Cambiamos al usuario seguro
USER appuser

EXPOSE 8000

# 5. Arrancamos uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]