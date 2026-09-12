from pathlib import Path

import yaml
from pydantic import BaseModel


class Model(BaseModel):
    chat: str
    embedding: str
    embedding_dimensions: int


class Agent(BaseModel):
    temperature: float
    max_iterations: int
    system_prompt_path: str

class Retrieval(BaseModel):
    collection_name: str
    top_k: int

class Timeouts(BaseModel):
    http_seconds: float

class AppConfig(BaseModel):
    model: Model
    agent: Agent
    retrieval: Retrieval
    timeouts: Timeouts


def load_config(path: str) -> AppConfig:
    config_path = Path(path).expanduser().resolve()

    with config_path.open("r", encoding="utf-8") as file:
        raw_config = yaml.safe_load(file)

    return AppConfig.model_validate(raw_config)