from fastmcp import FastMCP
from pymongo import MongoClient
import os
import json
from bson import json_util
from typing import Dict, Any # Quitamos Optional de aquí

# Definición del servidor
mcp = FastMCP("CineMCP")

# Conexión BD
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["sample_mflix"]

@mcp.tool()
def run_aggregation(
    collection_name: str, 
    pipeline_json: str,
    # --- CORRECCIÓN ---
    # Usamos tipos estrictos con valores por defecto. 
    # Esto genera un esquema "type": "integer" (o string/object) limpio, sin unions.
    update_id: int = 0,             
    message: Dict[str, Any] = {},   
    toolCallId: str = ""            
) -> str:
    """
    Ejecuta un pipeline de agregación en MongoDB.
    Args:
        collection_name: 'movies', 'comments', etc.
        pipeline_json: Array JSON. Ej: '[{"$match": ...}]'
        update_id: Ignorado.
        message: Ignorado.
        toolCallId: Ignorado.
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

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)