from fastmcp import FastMCP
from pymongo import MongoClient
import os
import json
from bson import json_util
from typing import Dict, Any
import certifi

# Imports del sistema
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Scope, Receive, Send

# 1. Definición del servidor
mcp = FastMCP("CineMCP")

# 2. Middleware "Paranoico" (Fail-Close)
class ParanoidMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app
        # Leemos la clave UNA sola vez al inicio para ver si existe
        self.api_key = os.getenv("MCP_API_KEY")
        if not self.api_key:
            print("🚨 PELIGRO: NO SE DETECTÓ 'MCP_API_KEY' EN EL ENTORNO.")
            print("🚨 EL SERVIDOR RECHAZARÁ TODAS LAS CONEXIONES POR SEGURIDAD.")

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        # Solo filtramos HTTP (dejamos pasar el ciclo de vida de la app)
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Excepción para Health Checks (para que Koyeb no mate el servicio)
        if scope["path"] in ["/", "/health"]:
            await self.app(scope, receive, send)
            return

        # --- LOGGING EN VIVO ---
        # Imprimimos quién intenta entrar
        print(f"🔒 ACCESO: Intento de conexión a ruta: {scope['path']}")

        # --- REGLA 1: SI NO HAY CLAVE CONFIGURADA EN KOYEB, NADIE ENTRA ---
        if not self.api_key:
            print("❌ BLOQUEADO: Error de configuración del servidor (Falta API Key)")
            response = JSONResponse(
                status_code=500, 
                content={"error": "SERVER SECURITY CONFIG ERROR: API Key missing in environment"}
            )
            await response(scope, receive, send)
            return

        # --- REGLA 2: VALIDAR EL HEADER ---
        headers = dict(scope.get("headers", []))
        auth_header_bytes = headers.get(b"authorization", b"")
        auth_header = auth_header_bytes.decode("utf-8")
        
        # Debemos ser estrictos: "Bearer <CLAVE>"
        expected_token = f"Bearer {self.api_key}"

        if auth_header != expected_token:
            # Chivato en los logs para ver qué enviaron (ocultando parte por seguridad)
            received_preview = auth_header[:10] + "..." if auth_header else "EMPTY"
            print(f"❌ BLOQUEADO: Credencial inválida. Recibido: '{received_preview}'")
            
            response = JSONResponse(
                status_code=401, 
                content={"error": "Unauthorized: Access Denied"}
            )
            await response(scope, receive, send)
            return

        # Si pasa todo, entra
        print("✅ ACCESO CONCEDIDO")
        await self.app(scope, receive, send)

# 3. Inyección Robusta
# Buscamos la app oculta de FastMCP
app_found = None
possible_attrs = ['_fastapi_app', 'fastapi_app', '_http_app', 'http_app']

for attr in possible_attrs:
    if hasattr(mcp, attr):
        app_found = getattr(mcp, attr)
        if callable(app_found):
             try:
                app_found = app_found()
             except:
                continue
        break

if app_found:
    print("🛡️ SEGURIDAD ACTIVADA: Inyectando Middleware Paranoico...")
    app_found.add_middleware(ParanoidMiddleware)
else:
    print("💀 ERROR CRÍTICO: No se pudo inyectar seguridad. El servidor está vulnerable.")

# 4. Base de Datos
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