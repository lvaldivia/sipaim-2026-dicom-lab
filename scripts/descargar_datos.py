"""Descarga las tres series públicas que utiliza el notebook y la aplicación."""
import subprocess
from pathlib import Path

from idc_index import IDCClient
import pydicom

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / "dcm_qa_ct"
if not REPO.exists():
    subprocess.run(["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", "https://github.com/neurolabusc/dcm_qa_ct", str(REPO)], check=True)
subprocess.run(["git", "sparse-checkout", "set", "In/GE", "In/Philips/S21570/S2020"], cwd=REPO, check=True)
destino = ROOT / "torax_lidc"
destino.mkdir(exist_ok=True)
cliente = IDCClient.client() if hasattr(IDCClient, "client") else IDCClient()
uid = "1.3.6.1.4.1.14519.5.2.1.6279.6001.100225287222365663678666836860"
cliente.download_from_selection(downloadDir=str(destino), seriesInstanceUID=uid)
for nombre, carpeta, esperado in [("GE", REPO / "In/GE", 28), ("Philips", REPO / "In/Philips/S21570/S2020", 140), ("LIDC-IDRI-1001", destino, 194)]:
    cantidad = 0
    for ruta in carpeta.rglob("*"):
        if not ruta.is_file():
            continue
        try:
            ds = pydicom.dcmread(ruta, force=True)
            if "ImagePositionPatient" in ds and ds.pixel_array.ndim == 2:
                cantidad += 1
        except Exception:
            continue
    print(nombre, "—", cantidad, "cortes válidos")
    assert cantidad == esperado, f"Descarga incompleta de {nombre}: se esperaban {esperado} cortes."
