import sys

from .. import payment_legacy as _legacy

sys.modules[__name__] = _legacy
