from fastmcp import FastMCP
from pymongo import MongoClient
import os
import json
from bson import json_util
from typing import Dict, Any
import certifi

# Imports necesarios
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Scope, Receive, Send

# 1. Definición del servidor
mcp = FastMCP("CineMCP")

# --- DEBUG CHIVATO ---
import sys
api_key = os.getenv("MCP_API_KEY")
print(f"--- DEBUG: Iniciando Servidor ---")
if api_key:
    print(f"--- DEBUG: Clave detectada: {api_key[:3]}*** (Longitud: {len(api_key)}) ---")
else:
    print("--- DEBUG: ALERTA!! No se detectó ninguna MCP_API_KEY en el entorno. El servidor está ABIERTO. ---")
# ---------------------

# 2. Middleware ASGI Puro (Compatible con Streaming/SSE)
class SecureASGIMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        # A. Solo interceptamos peticiones HTTP (dejamos pasar eventos de ciclo de vida)
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # B. Excluir Health Check (para que Koyeb no mate el servidor)
        if scope["path"] in ["/health", "/"]:
            await self.app(scope, receive, send)
            return

        # C. Lógica de Seguridad
        server_api_key = os.getenv("MCP_API_KEY")
        
        # Si hay clave configurada, verificamos
        if server_api_key:
            # En ASGI, los headers vienen en bytes y como lista de tuplas
            headers = dict(scope.get("headers", []))
            
            # Buscamos 'authorization' (siempre en minúsculas en ASGI)
            auth_header_bytes = headers.get(b"authorization", b"")
            auth_header = auth_header_bytes.decode("utf-8")
            
            expected = f"Bearer {server_api_key}"
            
            if auth_header != expected:
                # Si falla, cortamos aquí y devolvemos 401
                response = JSONResponse(
                    status_code=401, 
                    content={"error": "Unauthorized: Invalid API Key"}
                )
                await response(scope, receive, send)
                return

        # D. Si todo está bien, pasamos la bola a la app original (Streaming intacto)
        await self.app(scope, receive, send)

# 3. Inyección del Middleware
# Usamos .add_middleware con nuestra clase ASGI pura
if hasattr(mcp, '_fastapi_app'):
    mcp._fastapi_app.add_middleware(SecureASGIMiddleware)
else:
    print("WARNING: No se pudo inyectar seguridad. '_fastapi_app' no encontrado.")

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
        # Validación de seguridad extra: Evitar inyección en colecciones del sistema
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