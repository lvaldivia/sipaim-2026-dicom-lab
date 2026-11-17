"""Comprueba sintaxis, estructura y requisitos editoriales sin dependencias externas."""
import ast
import io
import json
import re
import tokenize
from pathlib import Path

ruta = Path(__file__).with_name("SIPAIM_2026_DICOM_Python.ipynb")
notebook = json.loads(ruta.read_text(encoding="utf-8"))
assert notebook["nbformat"] == 4
celdas = notebook["cells"]
codigos = 0
for indice, celda in enumerate(celdas):
    fuente = "".join(celda["source"])
    assert celda["id"]
    if celda["cell_type"] != "code":
        continue
    codigos += 1
    assert indice and celdas[indice - 1]["cell_type"] == "markdown", indice
    assert celda["execution_count"] is None and celda["outputs"] == []
    python = "\n".join(linea for linea in fuente.splitlines() if not linea.startswith("%"))
    ast.parse(python, filename=f"celda_{indice}")
    comentarios = {token.start[0] for token in tokenize.generate_tokens(io.StringIO(python).readline) if token.type == tokenize.COMMENT}
    for numero, linea in enumerate(python.splitlines(), start=1):
        assert not linea.strip() or numero in comentarios, f"Falta comentario en celda {indice}, línea {numero}"
texto = "\n".join("".join(c["source"]) for c in celdas)
enlaces = re.findall(r"\]\(#([^)]+)\)", texto)
for enlace in enlaces:
    assert f'id="{enlace}"' in texto, f"Enlace sin destino: {enlace}"
assert len(enlaces) == 8
markdown = "\n".join("".join(c["source"]) for c in celdas if c["cell_type"] == "markdown")
assert not re.search(r"\bminutos?\b|\bhoras?\b|≈\s*\d+\s*min\b", markdown, flags=re.I)
assert "no sirve para diagnóstico clínico" in markdown
assert texto.count("### Solución") == 2
assert "\"A\", 400, 1800" in texto and "\"B\", 40, 80" in texto and "\"C\", 40, 400" in texto
assert "enforce_file_format=True" in texto
assert not re.search(r"CARPETA_ZENODO|zenodo|PCIR|torso/", texto, flags=re.I)
print(f"Correcto: {len(celdas)} celdas, {codigos} bloques con sintaxis válida y comentarios por línea, {len(enlaces)} enlaces internos.")
print("Esta comprobación estática no equivale a ejecutar el notebook con los datos reales en Colab.")
