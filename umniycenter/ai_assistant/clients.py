
from .prompts import ADMIN_ASSISTANT_SYSTEM_PROMPT, DASHBOARD_INSIGHTS_PROMPT
from .services import OllamaClient


class AdminAIAssistant:
    def __init__(self):
        self.client = OllamaClient()

    def dashboard_insights(self, context_text):
        messages = [
            {
                "role": "system",
                "content": ADMIN_ASSISTANT_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": DASHBOARD_INSIGHTS_PROMPT + "\n\n" + context_text,
            },
        ]

        return self.client.chat(messages)
