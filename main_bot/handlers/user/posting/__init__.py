from aiogram import Router
from . import menu, channels, create_post, content


def get_router():
    from . import flow_content_plan
    routers = [
        menu.get_router(),
        channels.get_router(),
        create_post.get_router(),
        content.get_router(),
        flow_content_plan.get_router(),
    ]

    router = Router(name="Posting")
    router.include_routers(*routers)

    return router
