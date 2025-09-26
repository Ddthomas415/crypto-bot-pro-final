.PHONY: setup check build run bot jupyter dev logs clean stop shell ps restart rebuild update status reset-all help

setup:
	./scripts/setup_api_keys.sh

check:
	./scripts/check_api_keys.sh

build:
	./scripts/keychain_env.sh docker compose build --no-cache

run:
	./scripts/keychain_env.sh docker compose up -d

bot:
	./scripts/keychain_env.sh docker compose run -d --service-ports crypto-bot \
		streamlit run app/dashboard.py --server.port=8501 --server.address=0.0.0.0

jupyter:
	./scripts/keychain_env.sh docker compose run -d --service-ports crypto-bot \
		jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser --allow-root

dev:
	./scripts/keychain_env.sh docker compose run --service-ports --rm crypto-bot \
		streamlit run app/dashboard.py --server.port=8501 --server.address=0.0.0.0

logs:
	./scripts/keychain_env.sh docker logs -f crypto-bot

clean:
	./scripts/keychain_env.sh docker compose down -v || true

stop:
	./scripts/keychain_env.sh docker compose down || true

shell:
	./scripts/keychain_env.sh docker exec -it crypto-bot bash

ps:
	./scripts/keychain_env.sh docker compose ps

restart: stop run
	@echo "🔄 Restart complete!"

rebuild: clean build run
	@echo "🛠️ Rebuild complete! Fresh containers are up."

update:
	$(MAKE) rebuild

status: check ps
	@echo "📊 Status check complete."

reset-all:
	-security delete-generic-password -a "default" -s "crypto-bot-exchange-key" || true
	-security delete-generic-password -a "default" -s "crypto-bot-exchange-secret" || true
	./scripts/keychain_env.sh docker compose down -v || true
	@echo "💣 Full reset complete. Run 'make setup' to add API keys again."

help:
	@echo "Available targets: setup check build run bot jupyter dev logs clean stop shell ps restart rebuild update status reset-all help"
