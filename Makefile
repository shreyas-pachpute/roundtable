# Roundtable v0 · run the Harbor Logistics meeting locally
# Needs Python 3.11+ and Node 20+. No database server: SQLite in data/runtime.

PY ?= python
API_DIR = apps/api
UI_DIR = apps/meeting-room

.PHONY: install api ui meeting reset check

install:
	cd $(API_DIR) && $(PY) -m pip install -e .
	cd $(UI_DIR) && npm install

api:
	cd $(API_DIR) && $(PY) -m uvicorn roundtable.main:app --host 127.0.0.1 --port 8788

ui:
	cd $(UI_DIR) && npm run dev

# open a meeting on the demo RFP (the API must be running)
meeting:
	curl -s -X POST http://127.0.0.1:8788/api/meetings
	@echo "\nOpen http://localhost:3101"

reset:
	curl -s -X POST http://127.0.0.1:8788/api/demo/reset

check:
	curl -s http://127.0.0.1:8788/api/health
