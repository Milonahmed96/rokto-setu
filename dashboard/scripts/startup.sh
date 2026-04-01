#!/bin/bash
set -e

echo "Running database migrations..."
PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -f data/migrations/001_initial.sql 2>/dev/null || echo "Tables already exist"
PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -f data/migrations/002_indexes.sql 2>/dev/null || echo "Indexes already exist"

echo "Training ML models..."
python -m ml.forecasting --train
python -m ml.anomaly --train

echo "Starting API..."
uvicorn api.main:app --host 0.0.0.0 --port 8000