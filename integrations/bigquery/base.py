"""
Abstract interface for BigQuery / ERC-8004 integration.
live.py runs real SQL against the public Ethereum dataset.
mock.py reads from fixtures.
"""

from abc import ABC, abstractmethod
from typing import List
from core.models import Agent, EcosystemStats


class BigQueryClient(ABC):

    @abstractmethod
    def get_erc8004_agents(self) -> List[Agent]:
        """
        Return agents registered in the ERC-8004 Identity registry,
        joined with their Reputation registry scores.
        """
        ...

    @abstractmethod
    def get_ecosystem_stats(self) -> EcosystemStats:
        """
        Return aggregate stats across the full ERC-8004 dataset:
        total agents, x402 adoption, reputation distribution, growth.
        """
        ...
