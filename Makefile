format:
	uv run ruff format .

migrate:
# 	uv run alembic revision --autogenerate -m "Auto migration"
	uv run alembic upgrade head

run:
	make format 
	make migrate
	uv run main.py

# Evaluation commands
eval:
	@echo "🚀 Running evaluation (normal mode - shows only failures)..."
	uv run python -m evals.eval

eval-verbose:
	@echo "🚀 Running evaluation (verbose mode - shows all examples)..."
	uv run python -m evals.eval --verbose

eval-help:
	@echo "📖 Evaluation Commands:"
	@echo "  make eval         - Run evaluation (normal mode, shows only failed examples)"
	@echo "  make eval-verbose - Run evaluation (verbose mode, shows all examples)"
	@echo "  make eval-help    - Show this help message"

.PHONY: format migrate run eval eval-verbose eval-help