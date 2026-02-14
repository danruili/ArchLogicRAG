from flask import request, send_from_directory
from src.agent.chatbot import Chatbot
import os
from pathlib import Path


class Backend_Api:
    def __init__(self, app, config: dict) -> None:
        self.app = app
        self.config = config
        self.routes = {
            '/backend-api/v2/conversation': {
                'function': self._conversation,
                'methods': ['POST']
            },
            '/backend-api/v2/img/<path:subpath>': {
                'function': self._load_img,
                'methods': ['GET']
            }
        }
        # set_permissions(config['source_directory'])
        source_directory = config.get("source_directory", "data/wikiarch")
        index_directory = config.get("index_directory", "data/wikiarch/index")
        self.source_directory = source_directory
        self.index_directory = index_directory
        self.chatbot = None

    def _get_chatbot(self) -> Chatbot:
        if self.chatbot is None:
            self.chatbot = Chatbot(source_dir=self.source_directory, db_dir=self.index_directory)
        return self.chatbot


    def _conversation(self):
        try:
            prompt = request.json['meta']['content']['parts'][0]
            _conversation = request.json['meta']['content']['conversation']
            user_message = prompt["content"]
            chatbot = self._get_chatbot()
            chatbot.reset(_conversation)
            response = chatbot.cycle(user_message)
            return self.app.response_class(response)

        except Exception as e:
            print(e)
            print(e.__traceback__.tb_next)
            return {
                '_action': '_ask',
                'success': False,
                "error": f"an error occurred {str(e)}"}, 400

    def _load_img(self, subpath):
        try:
            # Supports either source_directory=data/wikiarch or data/wikiarch/raw.
            relative_path = Path(os.path.normpath(subpath))
            source_root = Path(self.config.get("source_directory", "data/wikiarch")).resolve()

            candidates = [
                source_root / relative_path,
                source_root / "raw" / relative_path,
            ]
            for full_path in candidates:
                if full_path.is_file():
                    return send_from_directory(str(full_path.parent), full_path.name)

            return {"success": False, "error": "image not found"}, 404
        except Exception as e:
            return {
                'success': False,
                "error": f"an error occurred {str(e)}"}, 400
        
PERMISSIONS = 0o755

def set_permissions(image_folder: str):
    """Ensure correct permissions for Flask to serve images."""
    # Change file permissions recursively
    for root, dirs, files in os.walk(image_folder):
        for directory in dirs:
            os.chmod(os.path.join(root, directory), PERMISSIONS)
        for file in files:
            os.chmod(os.path.join(root, file), PERMISSIONS)

    print(f"Permissions and ownership updated for {image_folder}")
