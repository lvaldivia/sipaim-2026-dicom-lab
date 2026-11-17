"""Prepara las mismas series públicas del notebook para la aplicación."""
import json
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))
from imaging import cargar_cortes, preparar_volumen, codificar_png

ORIGEN = ROOT.parent
DESTINO = ROOT / "data"
ESTUDIOS = [
    ("thorax", ORIGEN / "torax_lidc", "Tórax humano", "LIDC-IDRI-1001 · Siemens", -600, 1500, "CC BY 3.0 · Armato III y colaboradores / TCIA", "https://doi.org/10.7937/K9/TCIA.2015.LO9QL9SX"),
    ("head", ORIGEN / "dcm_qa_ct/In/GE", "Cerebro y cráneo", "CT humana · GE HiSpeed Dual", 40, 80, "BSD-2-Clause · Chris Rorden · GE cortesía de Aliza Medical Imaging", "https://github.com/neurolabusc/dcm_qa_ct"),
    ("phantom", ORIGEN / "dcm_qa_ct/In/Philips/S21570/S2020", "Fantoma de cráneo", "Maniquí · Philips Ingenuity", 400, 1800, "BSD-2-Clause · Chris Rorden · Philips cortesía de P. Morgan, Nottingham", "https://github.com/neurolabusc/dcm_qa_ct"),
]
manifest = []
for nombre, carpeta, titulo, subtitulo, nivel, ancho, licencia, enlace in ESTUDIOS:
    rutas = sorted(p for p in carpeta.rglob("*") if p.is_file())
    cortes, revision = cargar_cortes(rutas)
    volumen, meta = preparar_volumen(cortes, permitir_irregular=nombre == "head")
    indice = next(i for i, c in enumerate(cortes) if Path(c.filename).name == "18.dcm") if nombre == "head" else len(cortes) // 2
    meta.update({"id": nombre, "title": titulo, "subtitle": subtitulo, "default_level": nivel, "default_width": ancho, "default_index": indice, "license": licencia, "source_url": enlace, **revision})
    destino = DESTINO / nombre
    destino.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(destino / "volume.npz", hu=volumen)
    (destino / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    miniatura = ROOT / "frontend/assets" / (nombre + ".png")
    miniatura.parent.mkdir(parents=True, exist_ok=True)
    miniatura.write_bytes(codificar_png(volumen[indice], nivel, ancho))
    manifest.append(meta)
    print(nombre, volumen.shape, "MPR:", meta["mpr"], "tamaño comprimido:", (destino / "volume.npz").stat().st_size)
(DESTINO / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
shutil.copyfile(ORIGEN / "SIPAIM_2026_DICOM_Python.ipynb", ROOT / "frontend/assets/SIPAIM_2026_DICOM_Python.ipynb")
