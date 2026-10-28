from .core import create_app
from .genie import router as genie_router
from .matches import router as matches_router
from .router import router

app = create_app(routers=[router, genie_router, matches_router])
