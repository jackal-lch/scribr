.PHONY: dev stop setup db

# Start everything with one command
dev:
	./dev.sh

# First-time setup
setup:
	@echo "Setting up Scribr..."
	docker-compose up -d
	@echo "Installing backend dependencies..."
	cd backend && python -m venv .venv && \
		. .venv/bin/activate && \
		pip install -r requirements.txt
	@echo "Installing frontend dependencies..."
	cd frontend && npm install
	@echo "Running migrations..."
	cd backend && . .venv/bin/activate && alembic upgrade head
	@echo ""
	@echo "Setup complete! Run 'make dev' to start."

# Start only database
db:
	docker-compose up -d
