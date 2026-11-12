from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "hosa-api"
    app_version: str = "0.1.0"
    app_env: str = "local"
    log_level: str = "INFO"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    data_root: str = "../data"
    manifest_root: str = "../manifests"

    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")


settings = Settings()
