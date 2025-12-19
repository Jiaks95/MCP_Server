from mcp.server.fastmcp import FastMCP
from pymongo import MongoClient
import os
import json
from bson import json_util 

# Definición del servidor
mcp = FastMCP("CineMCP")

# Conexión BD
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["sample_mflix"]

@mcp.tool()
def run_aggregation(collection_name: str, pipeline_json: str) -> str:
    """
    Ejecuta un pipeline de agregación en MongoDB.
    Args:
        collection_name: 'movies', 'comments', etc.
        pipeline_json: Array JSON. Ej: '[{"$match": ...}]'
    """
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

# --- AQUÍ ESTÁ EL CAMBIO CLAVE ---
# Eliminamos la línea "app = mcp._http_server" que daba error.
# Y añadimos el bloque de ejecución directa:

if __name__ == "__main__":
    # Esto arranca el servidor SSE automáticamente en el puerto 8000
    # y escucha en 0.0.0.0 (necesario para Docker/Koyeb)
    mcp.run(transport="http", host="0.0.0.0", port=8000)