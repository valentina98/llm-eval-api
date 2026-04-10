from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str  # required — set DATABASE_URL in .env

    # Main LLM — used to generate responses
    # Format: "<provider>/<model>", e.g. "gemini/gemini-2.5-flash-lite", "ollama/tinyllama"
    llm_model: str | None = None
    llm_api_base: str | None = None  # required for local models, e.g. "http://ollama:11434"

    # Judge LLMs — used for the llm_judge test type
    # Cloud models only. Set API keys via standard provider env vars: GEMINI_API_KEY,
    # OPENAI_API_KEY, ANTHROPIC_API_KEY, etc. LiteLLM picks these up automatically.
    # LLM_JUDGE_MODELS=gemini/gemini-2.5-flash-lite,openai/gpt-4o-mini,anthropic/claude-haiku-4-5
    llm_judge_models: str | None = None

    # "extra": "ignore" — pydantic-settings parses .env directly and rejects unknown fields.
    # Provider keys (GEMINI_API_KEY etc.) live in .env for Docker/LiteLLM but have no field here.
    model_config = {"env_file": ".env", "extra": "ignore"}

    def get_judge_configs(self) -> list[str]:
        """Returns [model, ...] for all configured judges."""
        if not self.llm_judge_models:
            return []
        return [m.strip() for m in self.llm_judge_models.split(",") if m.strip()]


settings = Settings()
