from fastmcp import FastMCP
from pymongo import MongoClient
import os
import json
from bson import json_util
from typing import Dict, Any
import certifi

# Imports para Middleware (Starlette viene dentro de FastAPI/FastMCP)
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Scope, Receive, Send

# 1. Definición del servidor
mcp = FastMCP("CineMCP")

# 2. Middleware ASGI Puro (Compatible con Streaming/SSE)
class SecureASGIMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        # A. Solo interceptamos HTTP (dejamos pasar health checks y lifecycles)
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if scope["path"] in ["/health", "/"]:
            await self.app(scope, receive, send)
            return

        # B. Lógica de Seguridad
        server_api_key = os.getenv("MCP_API_KEY")
        
        if server_api_key:
            headers = dict(scope.get("headers", []))
            auth_header_bytes = headers.get(b"authorization", b"")
            auth_header = auth_header_bytes.decode("utf-8")
            
            # Validación estricta
            expected = f"Bearer {server_api_key}"
            
            if auth_header != expected:
                response = JSONResponse(
                    status_code=401, 
                    content={"error": "Unauthorized: Invalid API Key"}
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)

# 3. INYECCIÓN ROBUSTA DE SEGURIDAD
# Intentamos encontrar la app de FastAPI en varios lugares conocidos
app_found = None

# Lista de posibles nombres internos donde FastMCP esconde la app
possible_attrs = ['_fastapi_app', 'fastapi_app', '_http_app', 'http_app']

print("--- DEBUG: Buscando instancia de FastAPI ---")
for attr in possible_attrs:
    if hasattr(mcp, attr):
        print(f"--- DEBUG: Encontrada app en '{attr}' ---")
        app_found = getattr(mcp, attr)
        # Si es un método (como .http_app()), lo llamamos para obtener el objeto
        if callable(app_found):
             print(f"--- DEBUG: '{attr}' es un método, llamándolo... ---")
             try:
                app_found = app_found()
             except Exception as e:
                print(f"--- DEBUG: Error al llamar a {attr}: {e} ---")
                continue
        break

if app_found:
    print("--- SEGURIDAD: Inyectando Middleware... ---")
    app_found.add_middleware(SecureASGIMiddleware)
else:
    print("--- CRÍTICO: No se encontró la app subyacente. El servidor NO tiene seguridad. ---")
    # Imprimimos todos los atributos para que tú (el usuario) me los digas
    print(f"--- DEBUG DUMP: Atributos disponibles en 'mcp': {dir(mcp)} ---")

# 4. Conexión BD
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client["sample_mflix"]

@mcp.tool()
def run_aggregation(
    collection_name: str, 
    pipeline_json: str,
    update_id: int = 0,             
    message: Dict[str, Any] = {},   
    toolCallId: str = ""            
) -> str:
    try:
        if collection_name not in db.list_collection_names():
             return f"Error: La colección '{collection_name}' no existe."

        target_collection = db[collection_name]
        pipeline = json.loads(pipeline_json)
        cursor = target_collection.aggregate(pipeline)
        results = list(cursor)
        return json_util.dumps(results)

    except Exception as e:
        return f"Error ejecutando pipeline: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)