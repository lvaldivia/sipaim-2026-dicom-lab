"""Revisa los archivos preparados para Git sin imprimir posibles secretos."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
archivos = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
prohibidos = {".private", ".aws", ".venv", "node_modules", ".test-tools", ".build", "__pycache__", ".local"}
patrones = [rb"(?:AKIA|ASIA)[A-Z0-9]{16}", rb"gh[pousr]_[A-Za-z0-9]{25,}", rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"]
problemas = []
for nombre in filter(None, archivos):
    ruta = Path(nombre)
    if prohibidos.intersection(ruta.parts) or ruta.name.startswith(".env") or ruta.suffix.lower() in {".dcm", ".npz", ".pem", ".key", ".zip", ".mp3"}:
        problemas.append(nombre)
        continue
    if ruta.suffix.lower() in {".png", ".jpg", ".jpeg"}:
        continue
    contenido = (ROOT / ruta).read_bytes()
    if any(re.search(patron, contenido) for patron in patrones):
        problemas.append(nombre)
if problemas:
    raise SystemExit("Revise estos archivos antes del push: " + ", ".join(problemas))
print(f"Fuentes revisadas: {sum(bool(n) for n in archivos)} archivos; sin credenciales reconocibles ni datos/entornos excluidos.")
