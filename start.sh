#!/usr/bin/env bash

# Render provee la base de datos con el formato postgres://
# SQLAlchemy asíncrono y síncrono requieren un prefijo ligeramente diferente.
# Reemplazamos "postgres://" por "postgresql://" y "postgresql+asyncpg://" en tiempo de ejecución.

export SYNC_DATABASE_URL=$(python -c "import os; print(os.environ['RENDER_DB_URL'].replace('postgres://', 'postgresql://', 1))")
export DATABASE_URL=$(python -c "import os; url=os.environ['RENDER_DB_URL'].replace('postgres://', 'postgresql://', 1); print(url.replace('postgresql://', 'postgresql+asyncpg://', 1))")

echo "Ejecutando migraciones de Alembic..."
alembic upgrade head

echo "Iniciando servidor Uvicorn..."
# Render provee el puerto automáticamente a través de la variable $PORT
uvicorn app.main:app --host 0.0.0.0 --port $PORT
