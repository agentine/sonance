"""Compatibility shim for ``import sonance as pydub`` migration."""

from sonance.exceptions import SonanceException as PydubException

__all__ = ["PydubException"]
