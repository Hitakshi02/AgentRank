"""
Abstract interface for RAGAS evaluation integration.
live.py runs real RAGAS evaluation (LLM-as-judge) on a curated set.
mock.py reads pre-computed cached scores from fixtures.
"""

from abc import ABC, abstractmethod
from typing import Optional
from core.models import RagasScores


class RagasClient(ABC):

    @abstractmethod
    def evaluate(self, agent_id: str) -> Optional[RagasScores]:
        """
        Return RAGAS scores (faithfulness, answer_relevancy, context_precision)
        for the given agent, computed over a small fixed evaluation set.
        Returns None if the agent has no evaluation history.
        """
        ...
