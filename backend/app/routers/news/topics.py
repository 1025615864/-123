import sys

from .. import news_legacy as _legacy

sys.modules[__name__] = _legacy
