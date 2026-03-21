from dataclasses import dataclass


@dataclass(frozen=True)
class ActorIdentity:
    actor_id: str
    intent: str


def verify_identity(actor_id: str, intent: str) -> ActorIdentity:
    if not actor_id.strip():
        raise ValueError("actor_id is required")
    if not intent.strip():
        raise ValueError("intent is required")
    return ActorIdentity(actor_id=actor_id, intent=intent)
