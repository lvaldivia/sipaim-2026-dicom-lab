import io
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from imaging import ventana, seleccionar_plano, preparar_volumen, cargar_cortes, ImagingError
import handler as api


def test_ventana_conserva_hu_y_limita_el_rango():
    hu = np.array([-1000, 0, 40, 80, 2000], dtype=np.float32)
    original = hu.copy()
    assert ventana(hu, 40, 80).tolist() == [0, 0, 128, 255, 255]
    assert np.array_equal(hu, original)
    with pytest.raises(ImagingError):
        ventana(hu, 40, 0)


def test_coronal_invierte_z_y_conserva_proporcion_fisica():
    volumen = np.arange(3 * 4 * 5).reshape((3, 4, 5))
    plano, info = seleccionar_plano(volumen, {"spacing": [2, .5, .75], "mpr": True}, "coronal", 2)
    assert np.array_equal(plano[0], volumen[-1, 2])
    assert np.array_equal(plano[-1], volumen[0, 2])
    assert info["physical_aspect"] == 5 * .75 / (3 * 2)


@pytest.mark.skipif(not (ROOT.parent / "dcm_qa_ct/In/GE/18.dcm").exists(), reason="Ejecute scripts/descargar_datos.py para la prueba de GE con datos reales")
def test_ge_real_no_admite_mpr_y_18_conserva_calibracion():
    cortes, _ = cargar_cortes(sorted((ROOT.parent / "dcm_qa_ct/In/GE").glob("*.dcm")))
    volumen, meta = preparar_volumen(cortes, permitir_irregular=True)
    assert meta["mpr"] is False
    assert volumen.shape == (28, 512, 512)
    with pytest.raises(ImagingError):
        seleccionar_plano(volumen, meta, "coronal", 100)
    indice = next(i for i, ds in enumerate(cortes) if Path(ds.filename).name == "18.dcm")
    ds = cortes[indice]
    assert np.array_equal(volumen[indice], ds.pixel_array.astype(np.float32) * float(ds.RescaleSlope) + float(ds.RescaleIntercept))


def test_acceso_directo_no_requiere_clave(monkeypatch):
    monkeypatch.setattr(api, "cliente", lambda _: pytest.fail("No debe consultar AWS para la compatibilidad de sesión"))
    result = api.handler({"rawPath": "/api/session", "headers": {}, "requestContext": {"http": {"method": "POST"}}}, None)
    assert result["statusCode"] == 200
    assert json.loads(result["body"])["code_required"] is False


def test_medicion_pixel_no_depende_de_ventana(monkeypatch):
    volumen = np.array([[[0, 125], [-1000, 500]]], dtype=np.float32)
    monkeypatch.setattr(api, "cargar_estudio", lambda _: (volumen, {"spacing": [1, 1, 1], "mpr": True}))
    result = api.handler({"rawPath": "/api/pixel", "headers": {}, "requestContext": {"http": {"method": "GET"}}, "queryStringParameters": {"study": "head", "plane": "axial", "index": "0", "x": "1", "y": "0", "level": "-1000", "width": "10"}}, None)
    assert json.loads(result["body"])["hu"] == 125


def test_solicitud_explicita_ingles_prevalece_sobre_selector(monkeypatch):
    monkeypatch.setattr(api, "obtener_contexto", lambda _: (b"PNG", {"study": "demo"}))
    sistemas = []
    def completar(mensajes, sistema, max_tokens=650):
        sistemas.append(sistema)
        return "Educational explanation.", {}
    monkeypatch.setattr(api, "texto_modelo", completar)
    result = api.conversar({"question": "Explícalo en inglés", "language": "es"})
    assert result["language"] == "en"
    assert "entire answer in English" in sistemas[0]


def test_zip_ruta_no_permitida_se_rechaza_sin_aws(monkeypatch):
    monkeypatch.setattr(api, "cliente", lambda _: pytest.fail("No debe consultar almacenamiento para rutas inválidas"))
    with pytest.raises(ImagingError):
        api.importar({"key": "../otra-carpeta/secret.zip"})


def test_estudio_temporal_caducado_no_se_envia_a_bedrock(monkeypatch):
    monkeypatch.setattr(api, "cargar_estudio", lambda _: (np.zeros((3,4,4)), {"expires_at": 1}))
    monkeypatch.setattr(api, "cliente", lambda _: pytest.fail("No se debe enviar a AWS un estudio caducado"))
    with pytest.raises(ImagingError, match="caducado"):
        api.obtener_contexto({"study": "imported-" + "a" * 32})


def test_pregunta_de_seguimiento_conserva_seis_parejas_de_historial(monkeypatch):
    monkeypatch.setattr(api, "obtener_contexto", lambda _: (b"PNG", {"study": "demo"}))
    historial = []
    for i in range(8):
        historial.extend([{"role": "user", "text": f"pregunta {i}"}, {"role": "assistant", "text": f"respuesta {i}"}])
    capturado = []
    def completar(mensajes, sistema, max_tokens=900):
        capturado.extend(mensajes)
        return "Retomando tu respuesta anterior…", {}
    monkeypatch.setattr(api, "texto_modelo", completar)
    api.conversar({"question": "¿por qué?", "language": "es", "history": historial})
    assert len(capturado) == 13
    assert capturado[0]["content"][0]["text"] == "pregunta 2"
    assert capturado[-2]["content"][0]["text"] == "respuesta 7"
    assert "¿por qué?" in capturado[-1]["content"][-1]["text"]


def test_tutor_espera_respuesta_y_no_inventa_turno_del_alumno(monkeypatch):
    monkeypatch.setattr(api, "obtener_contexto", lambda _: (b"PNG", {"study":"demo"}))
    monkeypatch.setattr(api, "texto_modelo", lambda *args, **kwargs: ("Vamos a practicar. ¿Qué cambia al reducir el ancho? Tu respuesta: aumenta el contraste. Retroalimentación: correcto.", {}))
    resultado = api.conversar({"question":"Hazme una pregunta y espera mi respuesta.","language":"es"})
    assert resultado["answer"] == "¿Qué cambia al reducir el ancho?"
