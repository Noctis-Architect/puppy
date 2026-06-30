"""Backward compatibility — states moved to app.modules.*.states."""

from app.modules.admin.states import AdminStates
from app.modules.anonymous_reveal.states import AnonymousRevealStates
from app.modules.archive.states import DeletedMessagesStates
from app.modules.registration.states import RegistrationStates, UnregisterStates

__all__ = [
    "AdminStates",
    "AnonymousRevealStates",
    "DeletedMessagesStates",
    "RegistrationStates",
    "UnregisterStates",
]
