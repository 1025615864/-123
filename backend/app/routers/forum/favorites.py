import sys

from .. import forum_legacy as _legacy


async def _build_post_responses(db, posts, user_id):
    return [await _legacy._build_post_response(db, post, user_id) for post in posts]


_legacy._build_post_responses = _build_post_responses

sys.modules[__name__] = _legacy
