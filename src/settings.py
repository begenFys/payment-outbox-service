from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    backend_port: int = Field(...)

    pool_size: int = Field(8)
    max_overflow: int = Field(2)

    postgres_host: str = Field(...)
    postgres_host_port: int = Field(...)
    postgres_db: str = Field(...)
    postgres_user: str = Field(...)
    postgres_password: str = Field(...)

    rabbitmq_host: str = Field(...)
    rabbitmq_host_port: int = Field(...)
    rabbitmq_default_user: str = Field(...)
    rabbitmq_default_pass: str = Field(...)
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
