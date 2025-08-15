format:
	uv run ruff format .

migrate:
# 	uv run alembic revision --autogenerate -m "Auto migration"
	uv run alembic upgrade head
run:
	make format 
	make migrate
	uv run main.py