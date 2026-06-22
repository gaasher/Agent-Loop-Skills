"""Perplexity Sonar via OpenRouter — synthesized, cited answers for Level-1 high-level
questions ("how do people generally approach problem type X"). Needs OPENROUTER_API_KEY;
without it the CLI degrades to the agent's built-in WebSearch.
"""

import os

from ..http import request

URL = "https://openrouter.ai/api/v1/chat/completions"
MODELS = {
    "sonar": "perplexity/sonar",
    "sonar-pro": "perplexity/sonar-pro",
    "sonar-reasoning": "perplexity/sonar-reasoning",
}
SYSTEM = (
    "You are a meticulous ML research assistant. Answer with concrete, citable "
    "techniques and name the specific papers/methods. Prefer approaches with reported "
    "empirical gains and ablations. Be specific, not generic."
)


def ask(question, model="sonar"):
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    body = {
        "model": MODELS.get(model, "perplexity/sonar"),
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": question},
        ],
    }
    data = request(URL, method="POST", headers={"Authorization": "Bearer " + key},
                   body=body, bucket="default")
    choice = (data.get("choices") or [{}])[0]
    return {
        "source": "perplexity_sonar",
        "model": body["model"],
        "answer": (choice.get("message") or {}).get("content"),
        "citations": data.get("citations") or [],
    }
