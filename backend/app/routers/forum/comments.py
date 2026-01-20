import sys

from .. import forum_legacy as _legacy

sys.modules[__name__] = _legacy
