from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP
from pymongo import MongoClient
import uvicorn
import os
import json
from bson import json_util 

# Definición del servidor MCP
mcp = FastMCP("CineMCP")

# Conexión a Mongo usando Variable de Entorno
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["sample_mflix"]

@mcp.tool()
def run_aggregation(collection_name: str, pipeline_json: str) -> str:
    """
    Ejecuta un pipeline de agregación en MongoDB.
    
    Args:
        collection_name: Colección objetivo ('movies', 'comments', etc.)
        pipeline_json: String con el array JSON del pipeline. Ej: '[{"$match": ...}]'
    """
    try:
        if collection_name not in db.list_collection_names():
             return f"Error: La colección '{collection_name}' no existe."

        target_collection = db[collection_name]
        pipeline = json.loads(pipeline_json)
        
        # Ejecutamos la agregación
        cursor = target_collection.aggregate(pipeline)
        
        # Serializamos usando json_util para manejar ObjectIds y Fechas
        results = list(cursor)
        return json_util.dumps(results)

    except Exception as e:
        return f"Error ejecutando pipeline: {str(e)}"

app = mcp._http_server

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)