from fastmcp import FastMCP
from pymongo import MongoClient
import os
import json
from bson import json_util
from typing import Dict, Any
import certifi  # <--- IMPORTANTE: Importar certifi

# Definición del servidor
mcp = FastMCP("CineMCP")

# Conexión BD
MONGO_URI = os.getenv("MONGO_URI")

# --- CORRECCIÓN SSL ---
# Usamos certifi.where() para decirle a PyMongo dónde están los certificados seguros
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
    # ... (El resto de tu código sigue igual)
    try:
        # Una pequeña optimización: verificar conexión antes de operar
        # client.admin.command('ping') 
        
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