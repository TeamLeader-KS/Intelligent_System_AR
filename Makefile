.PHONY: up logs credentials stop

up:
	docker compose up -d

logs:
	docker compose logs -f backend apk bootstrap

credentials:
	docker compose logs bootstrap

stop:
	docker compose stop
