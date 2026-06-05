# Sotel Fit Core

Plataforma SaaS de personal training com IA.

## Stack

- Frontend: Next.js 15 + TypeScript + TailwindCSS (Vercel)
- Backend: FastAPI + Python 3.12 (Railway)
- Banco: PostgreSQL (Railway)
- Storage: Cloudflare R2
- DNS: Cloudflare

## Estrutura

    sotel-fit-core/
    apps/
      web/   -> Next.js 15
      api/   -> FastAPI
    packages/
    infrastructure/
    docs/
    .github/

## Backend

    cd apps\api
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    uvicorn app.main:app --reload

## Frontend

    cd apps\web
    npm install
    npm run dev

## Docker

    docker-compose up -d

## Branches

- main: producao
- staging: homologacao
- develop: desenvolvimento
- feature/*: features individuais

## Status da Migracao

- [ ] Fase 1 - Mapeamento e Fundacao
- [ ] Fase 2 - Frontend
- [ ] Fase 3 - Integracoes
- [ ] Fase 4 - Banco de Dados
- [ ] Fase 5 - Backend
- [ ] Fase 6 - DNS
- [ ] Fase 7 - Desativacao Base44
