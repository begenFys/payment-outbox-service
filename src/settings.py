from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    backend_port: int

    api_key: SecretStr

    pool_size: int = Field(8)
    max_overflow: int = Field(2)

    postgres_host: str
    postgres_host_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str

    rabbitmq_host: str
    rabbitmq_host_port: int
    rabbitmq_default_user: str
    rabbitmq_default_pass: str
    rabbitmq_prefetch_count: int = Field(10)

    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql+asyncpg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_host_port}"
            f"/{self.postgres_db}"
        )

    @property
    def rabbitmq_url(self) -> str:
        return (
            f"amqp://"
            f"{self.rabbitmq_default_user}:{self.rabbitmq_default_pass}"
            f"@{self.rabbitmq_host}:{self.rabbitmq_host_port}/"
        )


settings = Settings()  # type: ignore[call-arg]
