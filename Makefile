# Roundtable · run locally
# Python 3.12+ and Node 20+. Without DATABASE_URL the API uses SQLite in data/runtime; with a Postgres
# DATABASE_URL (Neon, Supabase, local) it uses Postgres, which is what production runs on.

PY ?= python
UI_DIR = apps/meeting-room

.PHONY: install api ui reset check deploy-api

install:
	$(PY) -m pip install -r requirements.txt
	cd $(UI_DIR) && npm install

api:
	$(PY) -m uvicorn app:app --host 127.0.0.1 --port 8788

ui:
	cd $(UI_DIR) && npm run dev

reset:
	curl -s -X POST http://127.0.0.1:8788/api/demo/reset

check:
	curl -s http://127.0.0.1:8788/api/health

# production: the API is a Vercel Python function, the UI a Vercel Next.js app
deploy-api:
	npx vercel deploy --prod
