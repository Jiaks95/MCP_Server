from fastmcp import FastMCP
from pymongo import MongoClient
import os
import json
from bson import json_util
from typing import Dict, Any
import certifi

# Imports para Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# 1. Definición del servidor
mcp = FastMCP("CineMCP")

# 2. Middleware de Autenticación
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Permitir health checks sin auth (opcional, buena práctica en Koyeb)
        if request.url.path == "/health":
             return await call_next(request)

        server_api_key = os.getenv("MCP_API_KEY")
        
        # Modo DEV: Si no hay clave configurada en el servidor, pasa todo
        if not server_api_key:
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        
        # Validación estricta: "Bearer TU_CLAVE"
        if not auth_header or auth_header != f"Bearer {server_api_key}":
            return JSONResponse(
                status_code=401, 
                content={"error": "Unauthorized: Invalid or missing API Key"}
            )
        
        return await call_next(request)

# 3. INYECCIÓN DEL MIDDLEWARE (CORREGIDO)
# Usamos _fastapi_app porque la librería lo mantiene como privado
if hasattr(mcp, '_fastapi_app'):
    mcp._fastapi_app.add_middleware(AuthMiddleware)
else:
    # Bloque de debug por si la librería cambia de versión
    print("ADVERTENCIA: No se pudo encontrar _fastapi_app. Buscando atributos disponibles...")
    print(dir(mcp)) 
    # Si ves esto en los logs, significa que el nombre interno es otro.

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
        
        # Opcional: Forzar límite aquí también por seguridad
        # pipeline.append({"$limit": 5})

        cursor = target_collection.aggregate(pipeline)
        results = list(cursor)
        return json_util.dumps(results)

    except Exception as e:
        return f"Error ejecutando pipeline: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)