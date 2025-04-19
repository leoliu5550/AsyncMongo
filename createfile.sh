mkdir -p ./app/config
mkdir -p ./app/api/endpoints
mkdir -p ./app/core
mkdir -p ./app/db/mongo
mkdir -p ./app/models
mkdir -p ./app/services
mkdir -p ./tests/test_api
mkdir -p ./tests/test_db

touch ./app/__init__.py
touch ./app/main.py
touch ./app/config/__init__.py
touch ./app/config/settings.py
touch ./app/api/__init__.py
touch ./app/api/endpoints/__init__.py
touch ./app/api/endpoints/users.py
touch ./app/api/endpoints/health.py
touch ./app/api/dependencies.py
touch ./app/core/__init__.py
touch ./app/core/events.py
touch ./app/db/__init__.py
touch ./app/db/mongo/__init__.py
touch ./app/db/mongo/client.py
touch ./app/db/mongo/factory.py
touch ./app/db/mongo/operations.py
touch ./app/db/mongo/repository.py
touch ./app/db/init_db.py
touch ./app/models/__init__.py
touch ./app/models/base.py
touch ./app/models/user.py
touch ./app/services/__init__.py
touch ./app/services/user_service.py
touch ./tests/__init__.py
touch ./tests/conftest.py
touch ./tests/test_api/__init__.py
touch ./tests/test_api/test_users.py
touch ./tests/test_db/__init__.py
touch ./tests/test_db/test_mongo_client.py
touch ./.env
touch ./.env.example
touch ./.gitignore
touch ./requirements.txt
touch ./pyproject.toml
touch ./README.md