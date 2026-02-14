from pathlib import Path
from flask import render_template, send_from_directory, redirect
from time import time
from os import urandom


class Website:
    def __init__(self, app) -> None:
        self.app = app
        self.templates_root = Path(__file__).resolve().parent / "templates"
        self.routes = {
            '/': {
                'function': lambda: redirect('/chat'),
                'methods': ['GET', 'POST']
            },
            '/chat/': {
                'function': self._index,
                'methods': ['GET', 'POST']
            },
            '/chat/<conversation_id>': {
                'function': self._chat,
                'methods': ['GET', 'POST']
            },
            '/assets/<folder>/<file>': {
                'function': self._assets,
                'methods': ['GET', 'POST']
            },
            '/favicon.ico': {
                'function': self._favicon,
                'methods': ['GET']
            }
        }

    def _chat(self, conversation_id):
        if not '-' in conversation_id:
            return redirect(f'/chat')

        return render_template('index.html', chat_id=conversation_id)

    def _index(self):
        return render_template('index.html', chat_id=f'{urandom(4).hex()}-{urandom(2).hex()}-{urandom(2).hex()}-{urandom(2).hex()}-{hex(int(time() * 1000))[2:]}')

    def _assets(self, folder: str, file: str):
        try:
            asset_dir = self.templates_root / folder
            return send_from_directory(str(asset_dir), file, as_attachment=False)
        except Exception:
            return "File not found", 404

    def _favicon(self):
        try:
            return send_from_directory(str(self.templates_root / "img"), "favicon.ico", as_attachment=False)
        except Exception:
            return "File not found", 404
