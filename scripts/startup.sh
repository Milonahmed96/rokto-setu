#!/bin/bash
set -e

echo "Running database migrations..."
python -c "
import asyncio, asyncpg, os

async def migrate():
    url = os.environ['DATABASE_URL'].replace('postgresql+asyncpg://', 'postgresql://')
    conn = await asyncpg.connect(url)
    with open('data/migrations/001_initial.sql') as f:
        await conn.execute(f.read())
    with open('data/migrations/002_indexes.sql') as f:
        await conn.execute(f.read())
    await conn.close()
    print('Migrations done')

asyncio.run(migrate())
" 2>/dev/null || echo "Migrations already applied"

echo "Training ML models..."
python -m data.generate --historical --hist-count 500
python -m ml.forecasting --train
python -m ml.anomaly --train

echo "Starting API..."
uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}