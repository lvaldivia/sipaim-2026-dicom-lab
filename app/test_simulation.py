"""Ejercita el SDK AWS real a través de los fallos HTTP servidos por Postman."""
import hashlib
import json
import os
import sys
from pathlib import Path
import boto3
import numpy as np
from botocore.config import Config

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
import handler as api
os.environ["APP_ACCESS_HASH"] = hashlib.sha256(b"simulation-only").hexdigest()
for servicio in ("bedrock-runtime", "polly"):
    api._clientes[servicio] = boto3.client(servicio, endpoint_url="http://127.0.0.1:8097/aws", region_name="us-east-1", aws_access_key_id="simulation-only", aws_secret_access_key="simulation-only", config=Config(retries={"total_max_attempts": 1}, read_timeout=3))
meta = {"title": "Test CT", "modality": "CT", "spacing": [2, 1, 1], "mpr": True, "geometry_note": "Simulation fixture"}
api.cargar_estudio = lambda _: (np.zeros((3, 4, 4), dtype=np.float32), meta)
for ruta, datos, esperado in [("chat", {"study":"thorax", "question":"Explica esta ventana", "language":"es", "index":1}, 429), ("speech", {"text":"Explicación educativa.", "language":"es", "source_language":"es"}, 503)]:
    evento = {"rawPath":"/api/" + ruta, "headers":{"x-app-key":"simulation-only"}, "requestContext":{"http":{"method":"POST"}}, "body":json.dumps(datos)}
    resultado = api.handler(evento, None)
    assert resultado["statusCode"] == esperado, resultado
    cuerpo = json.loads(resultado["body"])
    assert cuerpo["code"] == "upstream_unavailable"
    assert "answer" not in cuerpo and "audio" not in cuerpo
    print(ruta, resultado["statusCode"], cuerpo["code"], "— sin contenido de éxito inventado")
