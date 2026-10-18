import os

# Минимальный набор обязательных переменных для тестов
os.environ.setdefault("APP_DATABASE_URL", "postgresql://app:app@localhost:5432/app")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("JWT_SECRET", "test-secret")
