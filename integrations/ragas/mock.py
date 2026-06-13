"""
Mock RAGAS implementation.
Reads pre-computed scores from fixtures/agents.json - the "cache" pattern
described in the architecture. live.py would run real RAGAS once and
write to a similar cache file; mock.py just reads it.
"""

import json
from pathlib import Path
from typing import Optional
from integrations.ragas.base import RagasClient
from core.models import RagasScores

FIXTURES_PATH = Path(__file__).parent.parent.parent / "fixtures" / "agents.json"


class MockRagasClient(RagasClient):

    def evaluate(self, agent_id: str) -> Optional[RagasScores]:
        with open(FIXTURES_PATH) as f:
            data = json.load(f)
        for a in data["agents"]:
            if a["agent_id"] == agent_id:
                if a.get("ragas"):
                    return RagasScores(**a["ragas"])
                return None
        return None
