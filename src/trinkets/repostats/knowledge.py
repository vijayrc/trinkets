"""Curated mapping of package/image names to the infrastructure they imply.

This is the table that turns "the repo depends on psycopg2" into "the repo talks
to PostgreSQL", which is what both the dependency report and the flow diagram
are actually built on.  Keys are matched case-insensitively against the
*normalised* dependency name (lowercased, ``_`` -> ``-``).
"""

from __future__ import annotations

# Categories used throughout the report, in the order they should be displayed.
CATEGORY_ORDER: tuple[str, ...] = (
    "database",
    "cache",
    "messaging",
    "search",
    "web framework",
    "rpc",
    "http client",
    "task queue",
    "cloud",
    "observability",
    "auth",
    "data",
    "testing",
    "build",
    "other",
)

# Exact-name matches: normalised package name -> (category, canonical system).
PACKAGE_SYSTEMS: dict[str, tuple[str, str]] = {
    # --- databases -------------------------------------------------------
    "psycopg": ("database", "PostgreSQL"),
    "psycopg2": ("database", "PostgreSQL"),
    "psycopg2-binary": ("database", "PostgreSQL"),
    "asyncpg": ("database", "PostgreSQL"),
    "pg": ("database", "PostgreSQL"),
    "pg-promise": ("database", "PostgreSQL"),
    "postgres": ("database", "PostgreSQL"),
    "postgresql": ("database", "PostgreSQL"),
    "lib-pq": ("database", "PostgreSQL"),
    "mysqlclient": ("database", "MySQL"),
    "pymysql": ("database", "MySQL"),
    "mysql-connector-python": ("database", "MySQL"),
    "mysql2": ("database", "MySQL"),
    "mysql": ("database", "MySQL"),
    "mariadb": ("database", "MariaDB"),
    "sqlite3": ("database", "SQLite"),
    "better-sqlite3": ("database", "SQLite"),
    "aiosqlite": ("database", "SQLite"),
    "pymongo": ("database", "MongoDB"),
    "motor": ("database", "MongoDB"),
    "mongoose": ("database", "MongoDB"),
    "mongodb": ("database", "MongoDB"),
    "cassandra-driver": ("database", "Cassandra"),
    "scylla-driver": ("database", "ScyllaDB"),
    "neo4j": ("database", "Neo4j"),
    "influxdb-client": ("database", "InfluxDB"),
    "clickhouse-driver": ("database", "ClickHouse"),
    "clickhouse-connect": ("database", "ClickHouse"),
    "snowflake-connector-python": ("database", "Snowflake"),
    "google-cloud-bigquery": ("database", "BigQuery"),
    "duckdb": ("database", "DuckDB"),
    "cx-oracle": ("database", "Oracle"),
    "oracledb": ("database", "Oracle"),
    "pyodbc": ("database", "ODBC / SQL Server"),
    "pymssql": ("database", "SQL Server"),
    "boto3": ("cloud", "AWS"),
    "dynamodb": ("database", "DynamoDB"),

    # --- ORMs / data access ---------------------------------------------
    "sqlalchemy": ("database", "SQL (via SQLAlchemy)"),
    "alembic": ("database", "SQL migrations (Alembic)"),
    "django": ("web framework", "Django"),
    "peewee": ("database", "SQL (via Peewee)"),
    "tortoise-orm": ("database", "SQL (via Tortoise)"),
    "sqlmodel": ("database", "SQL (via SQLModel)"),
    "prisma": ("database", "SQL (via Prisma)"),
    "typeorm": ("database", "SQL (via TypeORM)"),
    "sequelize": ("database", "SQL (via Sequelize)"),
    "knex": ("database", "SQL (via Knex)"),
    "drizzle-orm": ("database", "SQL (via Drizzle)"),
    "gorm.io/gorm": ("database", "SQL (via GORM)"),
    "hibernate-core": ("database", "SQL (via Hibernate)"),
    "spring-boot-starter-data-jpa": ("database", "SQL (via Spring Data JPA)"),
    "diesel": ("database", "SQL (via Diesel)"),
    "sqlx": ("database", "SQL (via SQLx)"),

    # --- cache -----------------------------------------------------------
    "redis": ("cache", "Redis"),
    "aioredis": ("cache", "Redis"),
    "redis-py": ("cache", "Redis"),
    "ioredis": ("cache", "Redis"),
    "node-redis": ("cache", "Redis"),
    "jedis": ("cache", "Redis"),
    "lettuce-core": ("cache", "Redis"),
    "go-redis": ("cache", "Redis"),
    "pymemcache": ("cache", "Memcached"),
    "python-memcached": ("cache", "Memcached"),
    "memcached": ("cache", "Memcached"),
    "memjs": ("cache", "Memcached"),
    "hazelcast-python-client": ("cache", "Hazelcast"),
    "caffeine": ("cache", "Caffeine (in-process)"),

    # --- messaging -------------------------------------------------------
    "kafka-python": ("messaging", "Apache Kafka"),
    "confluent-kafka": ("messaging", "Apache Kafka"),
    "aiokafka": ("messaging", "Apache Kafka"),
    "kafkajs": ("messaging", "Apache Kafka"),
    "spring-kafka": ("messaging", "Apache Kafka"),
    "sarama": ("messaging", "Apache Kafka"),
    "pika": ("messaging", "RabbitMQ"),
    "aio-pika": ("messaging", "RabbitMQ"),
    "amqplib": ("messaging", "RabbitMQ"),
    "amqp": ("messaging", "RabbitMQ"),
    "kombu": ("messaging", "AMQP (Kombu)"),
    "nats-py": ("messaging", "NATS"),
    "pulsar-client": ("messaging", "Apache Pulsar"),
    "pyzmq": ("messaging", "ZeroMQ"),
    "paho-mqtt": ("messaging", "MQTT"),
    "google-cloud-pubsub": ("messaging", "Google Pub/Sub"),
    "azure-servicebus": ("messaging", "Azure Service Bus"),

    # --- task queues -----------------------------------------------------
    "celery": ("task queue", "Celery"),
    "rq": ("task queue", "RQ"),
    "dramatiq": ("task queue", "Dramatiq"),
    "bullmq": ("task queue", "BullMQ"),
    "bull": ("task queue", "Bull"),
    "sidekiq": ("task queue", "Sidekiq"),
    "apache-airflow": ("task queue", "Airflow"),
    "prefect": ("task queue", "Prefect"),

    # --- search ----------------------------------------------------------
    "elasticsearch": ("search", "Elasticsearch"),
    "opensearch-py": ("search", "OpenSearch"),
    "meilisearch": ("search", "Meilisearch"),
    "algoliasearch": ("search", "Algolia"),
    "pysolr": ("search", "Apache Solr"),
    "typesense": ("search", "Typesense"),

    # --- web frameworks --------------------------------------------------
    "flask": ("web framework", "Flask"),
    "fastapi": ("web framework", "FastAPI"),
    "starlette": ("web framework", "Starlette"),
    "quart": ("web framework", "Quart"),
    "sanic": ("web framework", "Sanic"),
    "tornado": ("web framework", "Tornado"),
    "bottle": ("web framework", "Bottle"),
    "pyramid": ("web framework", "Pyramid"),
    "falcon": ("web framework", "Falcon"),
    "aiohttp": ("web framework", "aiohttp"),
    "express": ("web framework", "Express"),
    "koa": ("web framework", "Koa"),
    "fastify": ("web framework", "Fastify"),
    "@nestjs/core": ("web framework", "NestJS"),
    "next": ("web framework", "Next.js"),
    "nuxt": ("web framework", "Nuxt"),
    "react": ("web framework", "React"),
    "vue": ("web framework", "Vue"),
    "@angular/core": ("web framework", "Angular"),
    "svelte": ("web framework", "Svelte"),
    "hapi": ("web framework", "hapi"),
    "spring-boot-starter-web": ("web framework", "Spring Boot"),
    "spring-boot-starter-webflux": ("web framework", "Spring WebFlux"),
    "spring-boot-starter": ("web framework", "Spring Boot"),
    "quarkus": ("web framework", "Quarkus"),
    "micronaut": ("web framework", "Micronaut"),
    "dropwizard-core": ("web framework", "Dropwizard"),
    "gin-gonic/gin": ("web framework", "Gin"),
    "labstack/echo": ("web framework", "Echo"),
    "gofiber/fiber": ("web framework", "Fiber"),
    "gorilla/mux": ("web framework", "Gorilla Mux"),
    "actix-web": ("web framework", "Actix Web"),
    "axum": ("web framework", "Axum"),
    "rocket": ("web framework", "Rocket"),
    "rails": ("web framework", "Ruby on Rails"),
    "sinatra": ("web framework", "Sinatra"),
    "laravel/framework": ("web framework", "Laravel"),
    "symfony/framework-bundle": ("web framework", "Symfony"),

    # --- servers ---------------------------------------------------------
    "gunicorn": ("web framework", "Gunicorn (WSGI server)"),
    "uvicorn": ("web framework", "Uvicorn (ASGI server)"),
    "hypercorn": ("web framework", "Hypercorn (ASGI server)"),
    "waitress": ("web framework", "Waitress (WSGI server)"),

    # --- rpc / api -------------------------------------------------------
    "grpcio": ("rpc", "gRPC"),
    "grpcio-tools": ("rpc", "gRPC"),
    "grpc": ("rpc", "gRPC"),
    "google.golang.org/grpc": ("rpc", "gRPC"),
    "protobuf": ("rpc", "Protocol Buffers"),
    "graphene": ("rpc", "GraphQL"),
    "strawberry-graphql": ("rpc", "GraphQL"),
    "graphql": ("rpc", "GraphQL"),
    "apollo-server": ("rpc", "GraphQL (Apollo)"),
    "@apollo/client": ("rpc", "GraphQL (Apollo)"),
    "thrift": ("rpc", "Apache Thrift"),

    # --- http clients ----------------------------------------------------
    "requests": ("http client", "HTTP (requests)"),
    "httpx": ("http client", "HTTP (httpx)"),
    "urllib3": ("http client", "HTTP (urllib3)"),
    "axios": ("http client", "HTTP (axios)"),
    "node-fetch": ("http client", "HTTP (node-fetch)"),
    "got": ("http client", "HTTP (got)"),
    "okhttp": ("http client", "HTTP (OkHttp)"),
    "retrofit": ("http client", "HTTP (Retrofit)"),
    "reqwest": ("http client", "HTTP (reqwest)"),

    # --- cloud -----------------------------------------------------------
    "botocore": ("cloud", "AWS"),
    "aioboto3": ("cloud", "AWS"),
    "aws-sdk": ("cloud", "AWS"),
    "@aws-sdk/client-s3": ("cloud", "AWS S3"),
    "google-cloud-storage": ("cloud", "Google Cloud Storage"),
    "google-cloud-core": ("cloud", "Google Cloud"),
    "azure-storage-blob": ("cloud", "Azure Blob Storage"),
    "azure-identity": ("cloud", "Azure"),
    "kubernetes": ("cloud", "Kubernetes API"),
    "docker": ("cloud", "Docker API"),
    "minio": ("cloud", "MinIO / S3"),

    # --- observability ---------------------------------------------------
    "sentry-sdk": ("observability", "Sentry"),
    "@sentry/node": ("observability", "Sentry"),
    "opentelemetry-api": ("observability", "OpenTelemetry"),
    "opentelemetry-sdk": ("observability", "OpenTelemetry"),
    "prometheus-client": ("observability", "Prometheus"),
    "prom-client": ("observability", "Prometheus"),
    "datadog": ("observability", "Datadog"),
    "ddtrace": ("observability", "Datadog"),
    "statsd": ("observability", "StatsD"),
    "structlog": ("observability", "Structured logging"),
    "winston": ("observability", "Logging (winston)"),
    "pino": ("observability", "Logging (pino)"),
    "loguru": ("observability", "Logging (loguru)"),
    "micrometer-core": ("observability", "Micrometer"),

    # --- auth ------------------------------------------------------------
    "pyjwt": ("auth", "JWT"),
    "jsonwebtoken": ("auth", "JWT"),
    "python-jose": ("auth", "JOSE/JWT"),
    "authlib": ("auth", "OAuth"),
    "passlib": ("auth", "Password hashing"),
    "bcrypt": ("auth", "bcrypt"),
    "passport": ("auth", "Passport"),
    "spring-boot-starter-security": ("auth", "Spring Security"),
    "oauthlib": ("auth", "OAuth"),

    # --- data / ml -------------------------------------------------------
    "pandas": ("data", "pandas"),
    "numpy": ("data", "NumPy"),
    "polars": ("data", "Polars"),
    "pyspark": ("data", "Apache Spark"),
    "dask": ("data", "Dask"),
    "scikit-learn": ("data", "scikit-learn"),
    "torch": ("data", "PyTorch"),
    "tensorflow": ("data", "TensorFlow"),
    "transformers": ("data", "Hugging Face Transformers"),
    "langchain": ("data", "LangChain"),
    "openai": ("data", "OpenAI API"),
    "anthropic": ("data", "Anthropic API"),

    # --- testing ---------------------------------------------------------
    "pytest": ("testing", "pytest"),
    "pytest-cov": ("testing", "pytest-cov"),
    "unittest2": ("testing", "unittest"),
    "nose": ("testing", "nose"),
    "hypothesis": ("testing", "Hypothesis"),
    "tox": ("testing", "tox"),
    "coverage": ("testing", "coverage.py"),
    "jest": ("testing", "Jest"),
    "vitest": ("testing", "Vitest"),
    "mocha": ("testing", "Mocha"),
    "chai": ("testing", "Chai"),
    "jasmine": ("testing", "Jasmine"),
    "cypress": ("testing", "Cypress"),
    "playwright": ("testing", "Playwright"),
    "@playwright/test": ("testing", "Playwright"),
    "selenium": ("testing", "Selenium"),
    "junit": ("testing", "JUnit"),
    "junit-jupiter": ("testing", "JUnit 5"),
    "spring-boot-starter-test": ("testing", "Spring Boot Test"),
    "mockito-core": ("testing", "Mockito"),
    "testcontainers": ("testing", "Testcontainers"),
    "rspec": ("testing", "RSpec"),
    "testify": ("testing", "testify"),
    "nyc": ("testing", "nyc (coverage)"),
    "istanbul": ("testing", "Istanbul (coverage)"),
    "jacoco": ("testing", "JaCoCo (coverage)"),
}

# Substring fallbacks, tried when there is no exact match.
SUBSTRING_SYSTEMS: tuple[tuple[str, str, str], ...] = (
    ("postgres", "database", "PostgreSQL"),
    ("mysql", "database", "MySQL"),
    ("sqlite", "database", "SQLite"),
    ("mongo", "database", "MongoDB"),
    ("cassandra", "database", "Cassandra"),
    ("dynamodb", "database", "DynamoDB"),
    ("clickhouse", "database", "ClickHouse"),
    ("redis", "cache", "Redis"),
    ("memcache", "cache", "Memcached"),
    ("kafka", "messaging", "Apache Kafka"),
    ("rabbitmq", "messaging", "RabbitMQ"),
    ("pubsub", "messaging", "Pub/Sub"),
    ("elasticsearch", "search", "Elasticsearch"),
    ("opensearch", "search", "OpenSearch"),
    ("opentelemetry", "observability", "OpenTelemetry"),
    ("prometheus", "observability", "Prometheus"),
    ("sentry", "observability", "Sentry"),
    ("grpc", "rpc", "gRPC"),
    ("graphql", "rpc", "GraphQL"),
    ("jwt", "auth", "JWT"),
    ("oauth", "auth", "OAuth"),
    ("boto", "cloud", "AWS"),
    ("aws-sdk", "cloud", "AWS"),
    ("azure-", "cloud", "Azure"),
    ("google-cloud", "cloud", "Google Cloud"),
    ("pytest", "testing", "pytest"),
    ("junit", "testing", "JUnit"),
    ("mock", "testing", "mocking library"),
)

# Docker image name -> (category, system). Matched against the image before the tag.
DOCKER_IMAGE_SYSTEMS: tuple[tuple[str, str, str], ...] = (
    ("postgres", "database", "PostgreSQL"),
    ("mysql", "database", "MySQL"),
    ("mariadb", "database", "MariaDB"),
    ("mongo", "database", "MongoDB"),
    ("redis", "cache", "Redis"),
    ("memcached", "cache", "Memcached"),
    ("elasticsearch", "search", "Elasticsearch"),
    ("opensearch", "search", "OpenSearch"),
    ("kafka", "messaging", "Apache Kafka"),
    ("redpanda", "messaging", "Redpanda"),
    ("zookeeper", "messaging", "ZooKeeper"),
    ("rabbitmq", "messaging", "RabbitMQ"),
    ("nats", "messaging", "NATS"),
    ("pulsar", "messaging", "Apache Pulsar"),
    ("localstack", "cloud", "LocalStack (AWS emulation)"),
    ("minio", "cloud", "MinIO / S3"),
    ("cassandra", "database", "Cassandra"),
    ("clickhouse", "database", "ClickHouse"),
    ("neo4j", "database", "Neo4j"),
    ("influxdb", "database", "InfluxDB"),
    ("prometheus", "observability", "Prometheus"),
    ("grafana", "observability", "Grafana"),
    ("jaeger", "observability", "Jaeger"),
    ("nginx", "other", "nginx"),
    ("traefik", "other", "Traefik"),
    ("vault", "auth", "HashiCorp Vault"),
    ("keycloak", "auth", "Keycloak"),
)

# Import statement fragment -> (category, system). Catches infrastructure that is
# used in code but declared transitively (or not at all) in the manifest.
IMPORT_SYSTEMS: tuple[tuple[str, str, str], ...] = (
    ("psycopg", "database", "PostgreSQL"),
    ("asyncpg", "database", "PostgreSQL"),
    ("pymongo", "database", "MongoDB"),
    ("sqlalchemy", "database", "SQL (via SQLAlchemy)"),
    ("sqlite3", "database", "SQLite"),
    ("redis", "cache", "Redis"),
    ("memcache", "cache", "Memcached"),
    ("kafka", "messaging", "Apache Kafka"),
    ("pika", "messaging", "RabbitMQ"),
    ("celery", "task queue", "Celery"),
    ("elasticsearch", "search", "Elasticsearch"),
    ("boto3", "cloud", "AWS"),
    ("grpc", "rpc", "gRPC"),
)


def normalise(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def classify_package(name: str) -> tuple[str, str] | None:
    """Return (category, canonical system) for a dependency name, if known."""
    key = normalise(name)
    if key in PACKAGE_SYSTEMS:
        return PACKAGE_SYSTEMS[key]

    # Java/Go coordinates: try the artifact id or final path segment.
    for separator in (":", "/"):
        if separator in key:
            tail = key.rsplit(separator, 1)[-1]
            if tail in PACKAGE_SYSTEMS:
                return PACKAGE_SYSTEMS[tail]

    for fragment, category, system in SUBSTRING_SYSTEMS:
        if fragment in key:
            return category, system
    return None


def classify_image(image: str) -> tuple[str, str] | None:
    """Return (category, system) for a container image reference."""
    ref = image.strip().lower().split("@", 1)[0]
    ref = ref.rsplit(":", 1)[0]        # drop tag
    ref = ref.rsplit("/", 1)[-1]       # drop registry/namespace
    for fragment, category, system in DOCKER_IMAGE_SYSTEMS:
        if fragment in ref:
            return category, system
    return None
