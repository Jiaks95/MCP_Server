from fastmcp import FastMCP
from pymongo import MongoClient
import os
import json
from bson import json_util
from typing import Dict, Any
import certifi
import uvicorn  # <--- IMPORTANTE: Importamos el servidor nosotros mismos

# Imports del sistema ASGI
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Scope, Receive, Send

# --- 1. Definición del servidor y Tools ---
mcp = FastMCP("CineMCP")

# Conexión Base de Datos
MONGO_URI = os.getenv("MONGO_URI")
# Fail-safe para local testing
if not MONGO_URI:
    MONGO_URI = "mongodb://localhost:27017" # Dummy
    
try:
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client["sample_mflix"]
except Exception as e:
    print(f"Error DB Connection: {e}")

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

# --- 2. Middleware de Seguridad (El Guardián) ---
class SecurityWrapper:
    def __init__(self, app: ASGIApp):
        self.app = app
        self.api_key = os.getenv("MCP_API_KEY")
        
        # Log inicial de estado
        if self.api_key:
            print(f"SEGURIDAD: Middleware cargado. Clave configurada (Longitud: {len(self.api_key)})")
        else:
            print("CRÍTICO: No hay MCP_API_KEY. El servidor rechazará todo por defecto.")

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        # Dejar pasar health checks y metadatos del protocolo
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "/")
        if path in ["/", "/health"]:
            await self.app(scope, receive, send)
            return

        # LOG CHIVATO: Para confirmar que el código se ejecuta
        print(f"INTERCEPTADO: Petición a {path}")

        # 1. Fail-Close: Si no hay clave en el servidor, error 500
        if not self.api_key:
            print("BLOQUEADO: Falta configuración de API Key en servidor.")
            response = JSONResponse(status_code=500, content={"error": "Server Security Config Missing"})
            await response(scope, receive, send)
            return

        # 2. Verificar Header
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode("utf-8")
        expected = f"Bearer {self.api_key}"

        if auth_header != expected:
            print(f"RECHAZADO: Credencial incorrecta.")
            response = JSONResponse(status_code=401, content={"error": "Unauthorized"})
            await response(scope, receive, send)
            return

        # 3. Éxito
        print("PASE CONCEDIDO")
        await self.app(scope, receive, send)


# --- 3. EXTRACCIÓN Y EMPAQUETADO (Aquí está el cambio clave) ---

# Intentamos sacar la app interna de FastMCP
internal_app = None
if hasattr(mcp, '_fastapi_app'):
    internal_app = mcp._fastapi_app
elif hasattr(mcp, 'fastapi_app'):
    internal_app = mcp.fastapi_app
elif hasattr(mcp, 'http_app'): # A veces es un método
     internal_app = mcp.http_app()

if not internal_app:
    raise RuntimeError("No se pudo extraer la aplicación FastAPI interna de FastMCP.")

# ENVOLVEMOS la app interna con nuestro guardián
# Esto crea una nueva app 'final_app' donde la entrada ES el middleware.
final_app = SecurityWrapper(internal_app)


# --- 4. EJECUCIÓN MANUAL ---
if __name__ == "__main__":
    # En lugar de mcp.run(), usamos uvicorn directamente sobre nuestra app protegida
    uvicorn.run(final_app, host="0.0.0.0", port=8000)