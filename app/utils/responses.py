from typing import Any


def success_response(message: str, data: Any = None) -> dict[str, Any]:
    return {"success": True, "message": message, "data": data}

