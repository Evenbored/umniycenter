import requests
from django.conf import settings

class OllamClient:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.model = settings.OLLAMA_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT
    
    def chat(self, messages, temperature=0.2):
        payload = {
            "model" : self.model,
            "messages": messages,
            "stream": False,
            "options":{
                "temperature": temperature,
            },
        }
        
        response = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=self.timeout,
        )
        
        response.raise_for_status()
        
        data = response.json()
        return data["message"]["content"]