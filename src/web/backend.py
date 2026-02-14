from flask import request, send_from_directory
from src.agent.chatbot import Chatbot
import os
from pathlib import Path
import threading
import time


class Backend_Api:
    def __init__(self, app, config: dict) -> None:
        self.app = app
        self.config = config
        self.routes = {
            '/backend-api/v2/conversation': {
                'function': self._conversation,
                'methods': ['POST']
            },
            '/backend-api/v2/progress/<request_id>': {
                'function': self._progress,
                'methods': ['GET']
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
        self._progress_store: dict[str, dict] = {}
        self._progress_lock = threading.Lock()

    def _get_chatbot(self) -> Chatbot:
        if self.chatbot is None:
            self.chatbot = Chatbot(source_dir=self.source_directory, db_dir=self.index_directory)
        return self.chatbot


    def _conversation(self):
        request_id = ""
        started_at = time.perf_counter()
        try:
            prompt = request.json['meta']['content']['parts'][0]
            _conversation = request.json['meta']['content']['conversation']
            request_id = str(request.json['meta'].get('id', ''))
            user_message = prompt["content"]
            chatbot = self._get_chatbot()
            chatbot.reset(_conversation)
            self._init_progress(request_id)
            response = chatbot.cycle(
                user_message,
                progress_callback=lambda msg: self._append_progress(request_id, msg),
            )
            self._finish_progress(request_id, response.get("progress_logs", []))
            return {
                "success": True,
                "content": response.get("content", ""),
                "progress_logs": response.get("progress_logs", []),
                "processing_time_ms": int((time.perf_counter() - started_at) * 1000),
            }

        except Exception as e:
            if request_id:
                self._finish_progress(request_id, [f"Failed: {str(e)}"])
            print(e)
            print(e.__traceback__.tb_next)
            return {
                '_action': '_ask',
                'success': False,
                "error": f"an error occurred {str(e)}"}, 400
    
    def _progress(self, request_id: str):
        self._cleanup_progress()
        with self._progress_lock:
            item = self._progress_store.get(request_id)
            if item is None:
                return {"success": True, "request_id": request_id, "done": False, "progress_logs": []}
            return {
                "success": True,
                "request_id": request_id,
                "done": bool(item.get("done", False)),
                "progress_logs": list(item.get("logs", [])),
            }

    def _init_progress(self, request_id: str) -> None:
        if not request_id:
            return
        with self._progress_lock:
            self._progress_store[request_id] = {
                "logs": [],
                "done": False,
                "updated_at": time.time(),
            }

    def _append_progress(self, request_id: str, message: str) -> None:
        if not request_id:
            return
        with self._progress_lock:
            item = self._progress_store.setdefault(
                request_id, {"logs": [], "done": False, "updated_at": time.time()}
            )
            item["logs"].append(message)
            item["updated_at"] = time.time()

    def _finish_progress(self, request_id: str, fallback_logs: list[str]) -> None:
        if not request_id:
            return
        with self._progress_lock:
            item = self._progress_store.setdefault(
                request_id, {"logs": [], "done": False, "updated_at": time.time()}
            )
            if not item["logs"] and fallback_logs:
                item["logs"] = list(fallback_logs)
            item["done"] = True
            item["updated_at"] = time.time()

    def _cleanup_progress(self, max_age_seconds: int = 3600) -> None:
        now = time.time()
        with self._progress_lock:
            stale_keys = [
                key
                for key, value in self._progress_store.items()
                if now - float(value.get("updated_at", now)) > max_age_seconds
            ]
            for key in stale_keys:
                self._progress_store.pop(key, None)

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
