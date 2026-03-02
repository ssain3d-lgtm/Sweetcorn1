import aiohttp
import asyncio
import json
import re
from typing import AsyncGenerator, List, Dict, Optional


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen3:14b", keep_alive: str = "10m"):
        self.base_url = base_url
        self.model = model
        self.keep_alive = keep_alive
        self.chat_endpoint = f"{base_url}/api/chat"

    async def is_available(self) -> bool:
        """Check if Ollama server is running"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    return resp.status == 200
        except Exception as e:
            print(f"Ollama availability check failed: {e}")
            return False

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        num_predict: int = 250
    ) -> AsyncGenerator[str, None]:
        """Stream chat response from Ollama"""

        # Prepare messages with system prompt
        formatted_messages = messages.copy()
        if system_prompt:
            formatted_messages.insert(0, {"role": "system", "content": system_prompt})

        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "stream": True,
            "think": False,           # Qwen3/exaone thinking 모드 비활성화
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_predict": num_predict,   # arousal별 동적 조절 (bot.py에서 전달)
                "repeat_penalty": 1.15,       # 반복 억제 (너무 높으면 garbage)
                "repeat_last_n": 256,
                "frequency_penalty": 0.1,     # 낮게 유지 (높으면 7.8B가 garbage 생성)
                "presence_penalty": 0.0,      # 비활성화 (7.8B 소형 모델에 위험)
                "top_k": 40,
                "min_p": 0.05,
                "stop": [                     # EOS 폭발 방지
                    "\n\n\n",
                    "User:",
                    "Assistant:",
                    "사용자:",
                    "하나:",
                    "Lee ",        # 영문 이름 단독 등장 차단 (garbage 방지)
                    "Daeseung",    # 유저 실명 garbage 방지
                ]
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.chat_endpoint,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    if resp.status != 200:
                        yield f"Error: Ollama API returned {resp.status}"
                        return

                    async for line in resp.content:
                        if line:
                            try:
                                chunk = json.loads(line.decode('utf-8'))
                                if 'message' in chunk and 'content' in chunk['message']:
                                    content = chunk['message']['content']
                                    if content:
                                        yield content
                                # thinking 필드는 무시 (Qwen3 thinking 모드 안전망)
                            except json.JSONDecodeError:
                                continue

        except asyncio.TimeoutError:
            yield "죄송합니다. 응답 시간이 초과되었습니다."
        except aiohttp.ClientConnectorError:
            yield "죄송합니다. Ollama 서버에 연결할 수 없습니다. 다음을 확인하세요:\n1. Ollama 서버가 실행 중인가요?\n2. http://localhost:11434 에 접속할 수 있나요?\n3. 모델이 다운로드되었나요? (ollama pull qwen3:14b)"
        except Exception as e:
            yield f"에러 발생: {str(e)}"

    @staticmethod
    def strip_thinking(text: str) -> str:
        """<think>...</think> 블록 제거 (Qwen3 thinking 모드 안전망)"""
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        return text.strip()

    async def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        top_p: float = 0.9
    ) -> str:
        """Get non-streaming chat response from Ollama"""

        response_text = ""
        async for chunk in self.chat_stream(messages, system_prompt, temperature, top_p):
            response_text += chunk

        return self.strip_thinking(response_text)

    def get_model_info(self) -> Dict[str, str]:
        """Get current model configuration"""
        return {
            "model": self.model,
            "base_url": self.base_url,
            "keep_alive": self.keep_alive
        }
