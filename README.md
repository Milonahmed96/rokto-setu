# 🩸 Rokto Setu — রক্ত সেতু

**Blood Bridge · AI-powered blood donor matching system · Bangladesh**

> Portfolio demonstration of production AI engineering — integrating 7 AI/ML techniques into a single coherent system around a real humanitarian problem. Not deployed publicly with real users. Uses 500 synthetic donor profiles.

[![CI](https://github.com/Milonahmed96/rokto-setu/actions/workflows/ci.yml/badge.svg)](https://github.com/Milonahmed96/rokto-setu/actions)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2.56-orange)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Docker](https://img.shields.io/badge/Docker-ready-blue)

**[🌐 Live Dashboard](https://rokto-setu.vercel.app)** · **[📋 Full Architecture Doc](https://github.com/Milonahmed96/rokto-setu/blob/main/docs/architecture.md)**

---

## What this is

Bangladesh has no government-backed blood donor database. People in emergencies — especially those needing rare blood groups like O− — die preventable deaths because they cannot find a donor in time.

Rokto Setu is a production-grade AI system that solves this with:
- A privacy-first donor matching platform built for Bangladesh's 4-tier geographic hierarchy
- An autonomous LangGraph agent that finds, ranks, and notifies eligible donors
- A PII scrubber that protects donor identity in anonymous chat relay
- A blood shortage forecasting model with calibrated uncertainty intervals
- An anomaly detector that flags fake or abusive requests

**Built as a portfolio demonstration of AI Engineering techniques — not deployed publicly.**

---

## 7 AI Techniques Demonstrated

| # | Technique | Component | From |
|---|-----------|-----------|------|
| 1 | **LangGraph Agent** | Autonomous donor matching, ranking, radius expansion | P6 Financial Agent |
| 2 | **Fine-tuned NER** | Bengali PII detection and scrubbing (94% F1) | P5 QLoRA fine-tuning |
| 3 | **RAG + pgvector** | Semantic donor search with multilingual embeddings | P4 RAG system |
| 4 | **LightGBM Forecasting** | District blood shortage prediction (7-day horizon) | P1 Rossmann |
| 5 | **Conformal Prediction** | Calibrated uncertainty intervals on forecasts | P3 Intervals |
| 6 | **Isolation Forest** | Fake request anomaly detection | MSc module |
| 7 | **PostGIS Geospatial** | 4-tier Bangladesh administrative hierarchy matching | New |

---

## Quick Start
```bash
git clone https://github.com/Milonahmed96/rokto-setu
cd rokto-setu
cp .env.example .env        # add your ANTHROPIC_API_KEY
docker compose up --build   # starts db + redis + api
```

Then open `http://localhost:8000/docs` for the interactive API docs.

To seed 500 synthetic donors:
```bash
python -m data.generate --count 500
python -m data.seed
```

To train the ML models:
```bash
python -m ml.forecasting --train
python -m ml.anomaly --train
```

---

## Project Structure
```
rokto-setu/
├── agent/          # LangGraph matching agent (graph, tools, state, prompts)
├── api/            # FastAPI backend + WebSocket chat relay
│   └── routes/     # auth, requests, match, chat, forecast, anomaly
├── ml/             # LightGBM forecasting + Isolation Forest anomaly detection
├── nlp/            # PII scrubber + NL request parser
├── data/           # Synthetic data generation + SQL migrations
├── dashboard/      # React demo frontend (deployed to Vercel)
├── tests/          # 80+ tests — NLP, forecasting, anomaly detection
└── docker-compose.yml
```

---

## Architecture
```
                    ┌─────────────────────────────────────┐
                    │         React Dashboard              │
                    │    rokto-setu.vercel.app             │
                    └──────────────┬──────────────────────┘
                                   │ HTTP
                    ┌──────────────▼──────────────────────┐
                    │         FastAPI Backend               │
                    │   /auth  /requests  /forecast        │
                    │   /match /chat      /anomaly         │
                    └──┬───────────┬──────────────────────┘
                       │           │
          ┌────────────▼───┐  ┌───▼──────────────────┐
          │  LangGraph     │  │  ML Models            │
          │  Matching      │  │  LightGBM Forecast    │
          │  Agent         │  │  Isolation Forest     │
          │                │  │  Conformal Prediction │
          └────────┬───────┘  └───────────────────────┘
                   │
          ┌────────▼───────┐  ┌───────────────────────┐
          │  PostgreSQL    │  │  NLP Pipeline         │
          │  + PostGIS     │  │  PII Scrubber         │
          │  + pgvector    │  │  Request Parser       │
          └────────────────┘  └───────────────────────┘
```

---

## Agent Demo

When a blood request is submitted, the LangGraph agent:
```
[AGENT] Starting matching for request d51c198c...
[AGENT] Blood group: O- | Urgency: EMERGENCY
[AGENT] Searching at tier: UPAZILA
[AGENT] Found 0 eligible donors at UPAZILA level
[AGENT] Expand decision: True — O- is rare, expanding to DISTRICT
[AGENT] Searching at tier: DISTRICT
[AGENT] Found 1 eligible donors at DISTRICT level
[AGENT] Expand decision: True — EMERGENCY urgency, expanding to DIVISION
[AGENT] Searching at tier: DIVISION
[AGENT] Found 3 eligible donors at DIVISION level
[AGENT] Notifying top 3 donors...
[AGENT] ✓ Donor 8d664945... accepted!
[AGENT] Complete — matched: True — 11 decision steps logged
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Phone OTP registration |
| POST | `/auth/verify-otp` | Verify OTP, get JWT |
| POST | `/requests/create` | Submit blood request → triggers agent |
| GET | `/requests/nearby` | Open requests in donor's area |
| POST | `/match/accept/:id` | Donor accepts → opens anonymous chat |
| POST | `/chat/:id/send` | Send message through PII scrubber |
| GET | `/forecast/district/:id` | 7-day shortage forecast + CI |
| POST | `/anomaly/score` | Score request for suspicious patterns |

---

## Test Suite
```bash
python -m pytest tests/ -v
# 80 tests — NLP scrubber, parser, forecasting, anomaly detection
```

---

## FinTech Relevance

Every component maps directly to banking/FinTech:

| Rokto Setu | FinTech Equivalent |
|------------|-------------------|
| Donor matching agent | Customer-product recommendation agent |
| PII scrubber | Transaction compliance filtering |
| Shortage forecasting | Credit demand forecasting |
| Conformal intervals | Risk model uncertainty quantification |
| Anomaly detection | Fraud detection |
| Agent observability | Audit trail for regulated decisions |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Orchestration | LangGraph + Claude API |
| Backend | FastAPI + Python 3.11 (async) |
| Database | PostgreSQL + PostGIS + pgvector |
| ML | LightGBM + scikit-learn + SHAP |
| NLP | spaCy + sentence-transformers |
| Real-time | Redis + WebSocket |
| Frontend | React + Vite + Recharts |
| MLOps | Docker + GitHub Actions CI |

---

## Portfolio Note

This project is a **portfolio demonstration** of AI Engineering techniques applied to a real humanitarian problem in Bangladesh. It is not deployed with real users — it uses 500 synthetic donor profiles generated via Claude API.

Built by **Milon Ahmed** — MSc Data Science with Advanced Research, University of Hertfordshire (2026). Targeting AI Engineer roles in London.

---

*Rokto Setu · রক্ত সেতু · Bangladesh · 2026*