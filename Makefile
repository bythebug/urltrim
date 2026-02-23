.PHONY: deps run worker test load docker-deps docker-up docker-down

deps:
	pip install -r requirements.txt

run:
	uvicorn main:app --reload

worker:
	python -m consumer

load:
	locust -f locustfile.py --host http://localhost:8000

docker-deps:
	docker-compose up -d postgres redis rabbitmq

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down
