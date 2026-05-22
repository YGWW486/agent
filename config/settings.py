from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 服务配置
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    WORKERS: int = 1

    # 队列配置
    QUEUE_MAXSIZE: int = 50

    # 超时配置
    DEFAULT_TIMEOUT_MS: int = 5000

    # LLM Provider
    LLM_PROVIDER: str = "anthropic"  # "anthropic" | "deepseek"

    # Anthropic 配置
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_DEFAULT_MODEL: str = "claude-sonnet-4-6"
    ANTHROPIC_MAX_TOKENS: int = 4096
    ANTHROPIC_THINKING_BUDGET: int = 16000

    # DeepSeek V4 配置 (2026-04-23 发布, openai>=1.30.0)
    # 模型: deepseek-v4-pro (1.6T/49B) | deepseek-v4-flash (284B/13B)
    # 旧 ID deepseek-chat/reasoner 将于 2026-07-24 下线
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_DEFAULT_MODEL: str = "deepseek-v4-pro"
    DEEPSEEK_MAX_TOKENS: int = 8192  # Planner/Coder 结构化 JSON 输出易超 4096
    DEEPSEEK_TEMPERATURE: float = 1.0  # DeepSeek 官方推荐 1.0，非 0.4-0.7
    DEEPSEEK_THINKING_MODE: str = "thinking"  # non-thinking | thinking | thinking_max

    # 模型分级
    MODEL_ROUTING: dict = {
        "simple": "claude-haiku-4-5-20251001",
        "standard": "claude-sonnet-4-6",
        "complex": "claude-opus-4-7",
    }

    # LangSmith 可观测性
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "agentic-qa"
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGSMITH_TRACING: bool = True

    # 重试配置
    MAX_RETRY_ATTEMPTS: int = 3
    INITIAL_RETRY_DELAY: float = 0.5
    MAX_RETRY_DELAY: float = 5.0

    # 熔断器配置
    CIRCUIT_BREAKER_THRESHOLD: int = 5
    CIRCUIT_BREAKER_RECOVERY: float = 60.0

    # Agent 工作流配置
    MAX_REVISIONS: int = 0  # 0 = 不限 Reviewer 修订轮次
    WORKFLOW_TIMEOUT: int = 300

    # Phase 1: Pipeline retry config
    PLANNER_RETRY_MAX: int = 1         # Planner 最多重试 1 次（2 次总尝试）
    PLANNER_RETRY_DELAY: float = 1.0   # Planner 重试初始延迟（秒）
    CODER_RETRY_MAX: int = 1           # Coder 最多自动重试 1 次
    CODER_RETRY_DELAY: float = 1.0     # Coder 重试初始延迟（秒）
    REVIEWER_RETRY_MAX: int = 0        # Reviewer 不自动重试（拒绝走 coder 回路）

    # GraphIndex 配置
    GRAPHIFY_OUT_DIR: str = ""
    GRAPH_JSON_PATH: str = ""
    GRAPH_INDEX_DB: str = "data/graph_index.db"

    # 成本控制
    DAILY_TOKEN_BUDGET: int = 1_000_000
    TASK_TOKEN_LIMIT: int = 100_000

    # 上下文预算（P2）
    PLANNER_CONTEXT_MAX_FILES: int = 30
    CODER_CONTEXT_DEPTH: int = 2
    CODER_CONTEXT_MAX_FILES: int = 15
    CONTEXT_MAX_CHARS: int = 24_000

    # Phase 4: Coder 只读 Tool Runtime
    CODER_TOOLS_ENABLED: bool = False
    CODER_TOOL_MAX_ROUNDS: int = 5
    WORKSPACE_ROOT: str = ""
    READ_FILE_MAX_BYTES: int = 65_536
    SEARCH_RG_MAX_RESULTS: int = 50
    SEARCH_RG_TIMEOUT_SEC: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
