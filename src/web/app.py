from pathlib import Path

from flask import Flask
from src.web.backend import Backend_Api
from src.web.website import Website

WEB_ROOT = Path(__file__).resolve().parent
TEMPLATE_ROOT = WEB_ROOT / "templates" / "html"

app = Flask(__name__, template_folder=str(TEMPLATE_ROOT))


def _register_route_map(flask_app: Flask, route_map: dict) -> None:
    for route, spec in route_map.items():
        endpoint_name = f"{spec['function'].__module__}.{spec['function'].__name__}.{route}"
        flask_app.add_url_rule(
            route,
            endpoint=endpoint_name,
            view_func=spec["function"],
            methods=spec.get("methods", ["GET"]),
        )


def _init_routes(flask_app: Flask) -> None:
    web = Website(flask_app)
    api = Backend_Api(
        flask_app,
        config={
            "source_directory": "data/wikiarch",
            "index_directory": "data/wikiarch/index",
        },
    )
    _register_route_map(flask_app, web.routes)
    _register_route_map(flask_app, api.routes)


_init_routes(app)
