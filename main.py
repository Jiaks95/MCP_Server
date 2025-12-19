from fastmcp import FastMCP
from pymongo import MongoClient
import os
import json
from bson import json_util
from typing import Dict, Any
import certifi

# Imports para el Middleware de Seguridad
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# 1. Definición del servidor
mcp = FastMCP("CineMCP")

# 2. Clase de Middleware de Autenticación
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Rutas excluidas (opcional, por si quieres dejar el health check libre)
        if request.url.path == "/health":
             return await call_next(request)

        server_api_key = os.getenv("MCP_API_KEY")
        
        # Si no hay variable de entorno, dejamos pasar (Modo Inseguro / Dev)
        if not server_api_key:
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        
        # Verificamos formato "Bearer <TOKEN>"
        if not auth_header or auth_header != f"Bearer {server_api_key}":
            return JSONResponse(
                status_code=401, 
                content={"error": "Unauthorized: Invalid or missing API Key"}
            )
        
        return await call_next(request)

# 3. Inyectamos el middleware en la app de FastAPI subyacente
# FastMCP usa FastAPI internamente, accedemos a la instancia así:
mcp.fastapi_app.add_middleware(AuthMiddleware)

# 4. Conexión BD (con Certifi para SSL)
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
    """
    Ejecuta un pipeline de agregación en MongoDB.
    """
    try:
        if collection_name not in db.list_collection_names():
             return f"Error: La colección '{collection_name}' no existe."

        target_collection = db[collection_name]
        pipeline = json.loads(pipeline_json)
        
        # Límite de seguridad forzado en código (opcional pero recomendado)
        # pipeline.append({"$limit": 5}) 
        
        cursor = target_collection.aggregate(pipeline)
        results = list(cursor)
        return json_util.dumps(results)

    except Exception as e:
        return f"Error ejecutando pipeline: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)