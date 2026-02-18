from .client import MeshtasticClient
from .dedupe import RequestDeduper
from .message import (
    MessageEnvelope,
    chunk_envelope,
    expand_payload,
    reconstruct_message,
    shorten_payload,
)
from .reassembly import MessageReassembler
from .transport import (
    InMemoryRadio,
    InMemoryRadioBus,
    MeshtasticTransport,
    RadioInterface,
)

# Note: this package is mirrored and released from the ATLAS monorepo via CI.

try:  # Optional dependency for API client
    from .gateway import MeshtasticGateway
except (
    ImportError,
    ModuleNotFoundError,
):  # pragma: no cover - optional import for lightweight usage/testing
    MeshtasticGateway = None  # type: ignore

__all__ = [
    "InMemoryRadio",
    "InMemoryRadioBus",
    "MessageEnvelope",
    "MessageReassembler",
    "MeshtasticClient",
    "MeshtasticGateway",
    "MeshtasticTransport",
    "RadioInterface",
    "RequestDeduper",
    "chunk_envelope",
    "reconstruct_message",
    "shorten_payload",
    "expand_payload",
]
