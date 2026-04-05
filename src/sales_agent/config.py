from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    agent_model: str = "claude-sonnet-4-6"
    max_pages_to_crawl: int = 10
    crawl_timeout: int = 30

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
