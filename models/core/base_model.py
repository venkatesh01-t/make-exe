from typing import Callable

class BaseModel:
    """Observable model — notify all registered listeners on change."""

    def __init__(self):
        self._listeners: dict[str, list[Callable]] = {}

    def on(self, event: str, callback: Callable):
        self._listeners.setdefault(event, []).append(callback)

    def off(self, event: str, callback: Callable):
        if event in self._listeners:
            self._listeners[event] = [
                c for c in self._listeners[event] if c != callback
            ]

    def emit(self, event: str, *args, **kwargs):
        for cb in self._listeners.get(event, []):
            try:
                cb(*args, **kwargs)
            except Exception as e:
                print(f"[Model] Error in listener for '{event}': {e}")

    def set_loading(self, state: bool):
        self.emit("loading", state)

    def set_error(self, message: str):
        self.emit("error", message)
