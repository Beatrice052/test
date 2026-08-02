"""Persistence-domain failures mapped to stable API error codes later."""


class PersistenceError(RuntimeError):
    pass


class OwnedObjectNotFound(PersistenceError):
    """Object is absent or is not owned by the requesting subject."""


class SessionArchived(PersistenceError):
    pass


class VersionConflict(PersistenceError):
    pass


class IdempotencyConflict(PersistenceError):
    pass


class SessionLockConflict(PersistenceError):
    pass


class TurnCancelled(PersistenceError):
    """Raised when a cancelled turn attempts to advance or publish state."""
