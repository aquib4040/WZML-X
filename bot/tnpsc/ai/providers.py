from httpx import AsyncClient, HTTPError

from .base import AIProvider, AIRequest


class OpenAICompatibleProvider(AIProvider):
    def __init__(self, name, base_url, api_key, model, timeout=60):
        self.name, self.base_url, self.api_key = name, base_url.rstrip("/"), api_key
        self.model, self.timeout = model, timeout

    async def generate(self, request: AIRequest) -> str:
        if not self.api_key and self.name != "ollama":
            raise RuntimeError(f"{self.name} API key is not configured")
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        async with AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json={"model": self.model, "messages": messages, "temperature": request.temperature, "max_tokens": request.max_tokens},
            )
            response.raise_for_status()
            data = response.json()
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError("AI provider returned an invalid response") from error


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, api_key, model, timeout=60):
        self.api_key, self.model, self.timeout = api_key, model, timeout

    async def generate(self, request: AIRequest) -> str:
        if not self.api_key:
            raise RuntimeError("Gemini API key is not configured")
        prompt = f"{request.system}\n\n{request.prompt}" if request.system else request.prompt
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        async with AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, params={"key": self.api_key}, json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": request.temperature, "maxOutputTokens": request.max_tokens}})
            response.raise_for_status()
            data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError("Gemini returned an invalid response") from error

