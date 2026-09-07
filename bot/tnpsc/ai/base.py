from dataclasses import dataclass


@dataclass
class AIRequest:
    prompt: str
    system: str = ""
    max_tokens: int = 700
    temperature: float = 0.2


class AIProvider:
    name = "base"

    async def generate(self, request: AIRequest) -> str:
        raise NotImplementedError

