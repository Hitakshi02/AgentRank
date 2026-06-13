"""
Abstract interface for BigQuery / ERC-8004 integration.
live.py runs real SQL against the public Ethereum dataset.
mock.py reads from fixtures.
"""

from abc import ABC, abstractmethod
from typing import Dict, List
from core.models import Agent, EcosystemStats
from core.scoring import FeedbackEvent, GiverStats


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

    @abstractmethod
    def get_feedback_for_scoring(self) -> List[FeedbackEvent]:
        """
        Return all FeedbackGiven events with decoded quality scores and
        giver addresses. Used by the Sybil-resistant scoring engine.
        Live implementation decodes ABI slot1 (quality score 0-100) from
        the event data field.
        """
        ...

    @abstractmethod
    def get_giver_wallet_stats(
        self, giver_addresses: List[str]
    ) -> Dict[str, GiverStats]:
        """
        Return wallet age (days since first tx) and tx count for each
        giver address. Used by the giver_credibility() scoring function.
        Live implementation joins to crypto_ethereum.transactions.
        Mock reads from fixtures/wallet_stats_cache.json.
        """
        ...

    @abstractmethod
    def get_domain_taxonomy(self) -> Dict[str, int]:
        """
        Return a mapping of domain name → agent count derived from
        AgentRegistered on-chain metadata (type URL fragment).
        Live: decodes base64 JSON from IdentityRegistry events.
        Mock: reads from fixtures/agents.json domain_taxonomy section.
        """
        ...
