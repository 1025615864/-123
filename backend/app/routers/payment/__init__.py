from .. import payment_legacy as _legacy

router = _legacy.router


def __getattr__(name: str):
    return getattr(_legacy, name)
