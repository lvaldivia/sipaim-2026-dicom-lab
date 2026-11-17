"""Vista previa local: mismo backend, datos locales y llamadas AWS reales."""
import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import boto3
import numpy as np
from aws_config import crear_sesion, nombre_stack, REGION

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))
import handler as api
session = crear_sesion()
deployment = ROOT / "deployment.json"
api.BUCKET = os.environ.get("DATA_BUCKET") or (json.loads(deployment.read_text())["Bucket"] if deployment.exists() else f"{nombre_stack()}-{session.client('sts').get_caller_identity()['Account']}-{REGION}")
api._clientes.update({name: session.client(name) for name in ["s3", "bedrock-runtime", "polly"]})
api_original = api.cargar_estudio

def datos_locales(nombre):
    if nombre.startswith("imported-"):
        return api_original(nombre)
    nombre = api.identificador(nombre)
    meta = json.loads((ROOT / "data" / nombre / "metadata.json").read_text(encoding="utf-8"))
    with np.load(ROOT / "data" / nombre / "volume.npz", allow_pickle=False) as archivo:
        volumen = archivo["hu"]
    return volumen, meta

from functools import lru_cache
api.cargar_estudio = lru_cache(maxsize=3)(datos_locales)

class LocalHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "frontend"), **kwargs)

    def dispatch(self):
        parsed = urlsplit(self.path)
        cuerpo = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8")
        evento = {"rawPath": parsed.path, "headers": dict(self.headers), "requestContext": {"http": {"method": self.command}}, "body": cuerpo, "queryStringParameters": {k: v[0] for k,v in parse_qs(parsed.query).items()}}
        if parsed.path == "/api/studies" and self.command == "GET":
            salida = api.respuesta({"studies":json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))})
        else:
            salida = api.handler(evento, None)
        self.send_response(salida["statusCode"])
        for clave, valor in salida["headers"].items():
            self.send_header(clave, valor)
        self.end_headers()
        self.wfile.write(salida["body"].encode("utf-8"))

    def do_GET(self):
        if self.path.startswith("/api/"):
            self.dispatch()
        else:
            super().do_GET()

    def do_POST(self):
        self.dispatch()

print("Vista previa: http://127.0.0.1:8765", flush=True)
ThreadingHTTPServer(("127.0.0.1", 8765), LocalHandler).serve_forever()
