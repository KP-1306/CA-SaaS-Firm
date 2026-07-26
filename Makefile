# CA Firm Operations SaaS — task runner
# Windows users without `make` can run the underlying commands directly.

.DEFAULT_GOAL := help
.PHONY: help install install-backend install-frontend check \
        backend-format backend-lint backend-types backend-django-check backend-test \
        frontend-format frontend-lint frontend-types frontend-test frontend-build \
        verify-structure secret-scan clean

PYTHON  := python3.12
BACKEND := backend
FRONTEND:= frontend

help: ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-26s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------- install ----
install: install-backend install-frontend ## Install all dependencies

install-backend: ## Install backend dependencies into the local virtualenv
	cd $(BACKEND) && $(PYTHON) -m venv .venv
	cd $(BACKEND) && .venv/bin/pip install --upgrade pip
	cd $(BACKEND) && .venv/bin/pip install -r requirements/development.txt

install-frontend: ## Install frontend dependencies from the lock file
	cd $(FRONTEND) && npm ci

# ------------------------------------------------------------------ checks ----
check: backend-format backend-lint backend-types backend-django-check backend-test \
       frontend-format frontend-lint frontend-types frontend-test frontend-build \
       verify-structure secret-scan ## Run every check

backend-format: ## Check Python formatting
	cd $(BACKEND) && .venv/bin/ruff format --check .

backend-lint: ## Lint Python
	cd $(BACKEND) && .venv/bin/ruff check .

backend-types: ## Type-check Python
	cd $(BACKEND) && .venv/bin/mypy .

backend-django-check: ## Django system check
	cd $(BACKEND) && .venv/bin/python manage.py check

backend-django-check-deploy: ## Django deployment check against production settings
	cd $(BACKEND) && DJANGO_SETTINGS_MODULE=config.settings.production \
	  DJANGO_SECRET_KEY=check-only-not-a-real-secret \
	  DJANGO_ALLOWED_HOSTS=example.invalid \
	  .venv/bin/python manage.py check --deploy

backend-test: ## Run backend tests
	cd $(BACKEND) && .venv/bin/pytest

frontend-format: ## Check frontend formatting
	cd $(FRONTEND) && npm run format:check

frontend-lint: ## Lint frontend
	cd $(FRONTEND) && npm run lint

frontend-types: ## Type-check frontend
	cd $(FRONTEND) && npm run typecheck

frontend-test: ## Run frontend tests
	cd $(FRONTEND) && npm run test:run

frontend-build: ## Production build
	cd $(FRONTEND) && npm run build

# ------------------------------------------------------------ verification ----
verify-structure: ## Verify the repository tree matches the frozen structure
	$(PYTHON) scripts/verify_structure.py

secret-scan: ## Scan tracked files for secret-like material
	$(PYTHON) scripts/secret_scan.py

# ------------------------------------------------------------------- clean ----
clean: ## Remove caches and build output (never touches .env or source)
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(FRONTEND)/dist
