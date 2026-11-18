from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_secret_key: str = "change-me"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    openai_api_key: str
    openai_llm_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = 1536

    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "agenttrust"
    keycloak_client_id: str = "agenttrust-backend"
    keycloak_client_secret: str = ""

    default_chunk_size: int = 512
    default_chunk_overlap: int = 50
    max_retrieval_chunks: int = 8


settings = Settings()
