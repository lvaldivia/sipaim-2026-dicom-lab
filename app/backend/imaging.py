"""Lectura y visualización DICOM; intensidades y mediciones se calculan en Python."""
import base64
import io
import json
from pathlib import Path

import numpy as np
import pydicom
from PIL import Image


class ImagingError(ValueError):
    pass


def cargar_cortes(archivos):
    """Agrupa por UID y elige la serie CT con más instancias utilizables."""
    grupos = {}
    descartados = 0
    for archivo in archivos:
        try:
            ds = pydicom.dcmread(archivo, force=True)
            if ds.get("Modality") != "CT" or "ImagePositionPatient" not in ds or "PixelSpacing" not in ds:
                descartados += 1
                continue
            if not (1 <= int(ds.get("Rows", 0)) <= 1024 and 1 <= int(ds.get("Columns", 0)) <= 1024) or int(ds.get("NumberOfFrames", 1)) != 1:
                descartados += 1
                continue
            if ds.pixel_array.ndim != 2:
                descartados += 1
                continue
            grupos.setdefault(str(ds.SeriesInstanceUID), []).append(ds)
        except Exception:
            descartados += 1
    if not grupos:
        raise ImagingError("No se encontraron cortes CT DICOM con posición, espaciado y píxeles decodificables.")
    cortes = max(grupos.values(), key=len)
    cortes.sort(key=lambda ds: float(ds.ImagePositionPatient[2]))
    return cortes, {"series_found": len(grupos), "discarded_files": descartados}


def preparar_volumen(cortes, permitir_irregular=False):
    """Conserva HU originales y comprueba si la serie admite MPR axial simple."""
    if len(cortes) < 2:
        raise ImagingError("Se necesitan al menos dos cortes para explorar la serie.")
    primero = cortes[0]
    posiciones = np.asarray([c.ImagePositionPatient for c in cortes], dtype=float)
    diferencias = np.diff(posiciones[:, 2])
    dz = float(np.median(diferencias))
    dy, dx = map(float, primero.PixelSpacing)
    orientacion = np.asarray(primero.get("ImageOrientationPatient", []), dtype=float)
    uniforme = dz > 0 and bool(np.allclose(diferencias, dz, atol=0.05, rtol=0.01))
    axial = orientacion.shape == (6,) and bool(np.allclose(orientacion, [1, 0, 0, 0, 1, 0], atol=0.01))
    sin_cizalla = bool(np.allclose(posiciones[:, :2], posiciones[0, :2], atol=0.1))
    consistentes = all(np.allclose(c.PixelSpacing, [dy, dx]) and (c.Rows, c.Columns) == (primero.Rows, primero.Columns) and np.allclose(c.get("ImageOrientationPatient", []), orientacion, atol=0.01) for c in cortes)
    if not consistentes:
        raise ImagingError("La serie cambia de matriz, orientación o espaciado entre imágenes.")
    mpr = uniforme and axial and sin_cizalla
    if not mpr and not permitir_irregular:
        raise ImagingError("Esta serie tiene geometría irregular, inclinada u oblicua; requiere remuestreo antes de MPR.")
    volumen = np.stack([c.pixel_array.astype(np.float32) * float(c.get("RescaleSlope", 1)) + float(c.get("RescaleIntercept", 0)) for c in cortes])
    # Se conservan únicamente atributos técnicos; no se trasladan identificadores del paciente.
    metadatos = {
        "shape": list(volumen.shape), "spacing": [dz, dy, dx], "slice_thickness": float(primero.get("SliceThickness", dz)),
        "slice_thicknesses": [float(c.get("SliceThickness", dz)) for c in cortes],
        "modality": "CT", "body_part": str(primero.get("BodyPartExamined", "No especificada")),
        "manufacturer": str(primero.get("Manufacturer", "No disponible")),
        "model": str(primero.get("ManufacturerModelName", "No disponible")),
        "mpr": mpr, "gantry_tilt": float(primero.get("GantryDetectorTilt", 0)),
        "geometry_note": "Rejilla axial regular; MPR con proporciones físicas." if mpr else "Gantry inclinado o posiciones irregulares: solo cortes axiales originales; MPR desactivada.",
        "slope_intercept_applied": True,
    }
    return volumen, metadatos


def ventana(hu, nivel, ancho):
    """Devuelve intensidades para PNG; los HU fuente se conservan sin modificación."""
    if not np.isfinite(nivel) or not np.isfinite(ancho) or not 1 <= ancho <= 5000 or not -2000 <= nivel <= 3000:
        raise ImagingError("Nivel o ancho de ventana fuera del rango admitido.")
    inferior = nivel - ancho / 2
    return np.rint((np.clip(hu, inferior, nivel + ancho / 2) - inferior) * (255 / ancho)).astype(np.uint8)


def seleccionar_plano(volumen, meta, plano, indice=None):
    if plano not in ("axial", "coronal", "sagittal"):
        raise ImagingError("Plano no reconocido.")
    if plano != "axial" and not meta["mpr"]:
        raise ImagingError(meta["geometry_note"])
    eje = {"axial": 0, "coronal": 1, "sagittal": 2}[plano]
    total = volumen.shape[eje]
    indice = total // 2 if indice is None else int(indice)
    if not 0 <= indice < total:
        raise ImagingError("Índice de corte fuera del volumen.")
    dz, dy, dx = meta["spacing"]
    if plano == "axial":
        imagen, paso = volumen[indice], [dy, dx]
    elif plano == "coronal":
        imagen, paso = volumen[::-1, indice, :], [dz, dx]
    else:
        imagen, paso = volumen[::-1, :, indice], [dz, dy]
    return imagen, {"plane": plano, "index": indice, "total": total, "image_spacing": paso, "image_shape": list(imagen.shape), "physical_aspect": imagen.shape[1] * paso[1] / (imagen.shape[0] * paso[0])}


def codificar_png(imagen, nivel, ancho):
    archivo = io.BytesIO()
    Image.fromarray(ventana(imagen, nivel, ancho)).save(archivo, format="PNG")
    return archivo.getvalue()


def frame(volumen, meta, plano, indice, nivel, ancho):
    imagen, contexto = seleccionar_plano(volumen, meta, plano, indice)
    png = codificar_png(imagen, nivel, ancho)
    contexto.update({"level": nivel, "width": ancho, "hu_min": float(imagen.min()), "hu_max": float(imagen.max())})
    return {**contexto, "image": "data:image/png;base64," + base64.b64encode(png).decode("ascii")}
