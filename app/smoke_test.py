"""Comprueba HTTPS, acceso, imágenes, Bedrock, Polly e importación reales."""
import base64
import hashlib
import io
import json
import os
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import pydicom
import requests
from PIL import Image
from aws_config import configurar_tls

ROOT = Path(__file__).resolve().parent
url = sys.argv[1] if len(sys.argv) > 1 else json.loads((ROOT / "deployment.json").read_text())["Url"]
configurar_tls()
ca = os.environ.get("AWS_CA_BUNDLE", True)
sesion = requests.Session()
sesion.verify = ca
resultados = []

def llamar(ruta, datos=None):
    headers = {}
    if datos is None:
        respuesta = sesion.get(url + "/api/" + ruta, headers=headers, timeout=100)
    else:
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        headers.update({"Content-Type":"application/json", "x-amz-content-sha256":hashlib.sha256(cuerpo).hexdigest()})
        respuesta = sesion.post(url + "/api/" + ruta, data=cuerpo, headers=headers, timeout=100)
    if not respuesta.ok:
        print("Fallo:", ruta, respuesta.status_code, respuesta.text[:500], flush=True)
    return respuesta

def registrar(nombre, valor=True):
    assert valor, nombre
    resultados.append(nombre)
    print("OK:", nombre, flush=True)

registrar("Frontend HTTPS", sesion.get(url + "/", timeout=45).status_code == 200)
registrar("Acceso directo sin código", llamar("studies").status_code == 200)
registrar("Sesión sin contraseña", llamar("session", {}).json().get("code_required") is False)
series = llamar("studies").json()["studies"]
registrar("Tres series públicas", {s["id"] for s in series} == {"head", "thorax", "phantom"})
for study in series:
    info = llamar("frame?study="+study["id"]+"&plane=axial&index="+str(study["default_index"])+"&level="+str(study["default_level"])+"&width="+str(study["default_width"])).json()
    imagen = Image.open(io.BytesIO(base64.b64decode(info["image"].split(",",1)[1])))
    registrar("PNG axial " + study["id"], imagen.size == (512,512))
registrar("MPR bloqueada para GE inclinado", llamar("frame?study=head&plane=coronal&index=200").status_code == 400)
coronal = llamar("frame?study=thorax&plane=coronal&index=256&level=-600&width=1500").json()
registrar("MPR con aspecto físico", abs(coronal["physical_aspect"] - (512*.64453125)/(194*1.8)) < .001)
pixel = llamar("pixel?study=head&plane=axial&index="+str(next(s["default_index"] for s in series if s["id"]=="head"))+"&x=256&y=256").json()
with np.load(ROOT / "data/head/volume.npz") as original:
    medido = float(original["hu"][next(s["default_index"] for s in series if s["id"]=="head"),256,256])
registrar("HU medidos coinciden con el volumen original", pixel["hu"] == medido)
contexto = {"study":"thorax", "plane":"axial", "index":97, "level":-600, "width":1500}
es = llamar("chat", {**contexto, "question":"Explica la ventana de pulmón y sus limitaciones en dos frases.", "language":"es"}).json()
registrar("Bedrock con imagen en español", bool(es.get("answer")) and es.get("language")=="es")
historial = [{"role":"user","text":"Explica la ventana de pulmón y sus limitaciones en dos frases."},{"role":"assistant","text":es["answer"]}]
quiz = llamar("chat", {**contexto,"question":"Ahora hazme una pregunta para practicar lo que acabas de explicar y espera mi respuesta.","language":"es","history":historial}).json()
registrar("El tutor hace una pregunta y espera sin inventar la respuesta", bool(quiz.get("answer")) and quiz["answer"].endswith("?") and quiz["answer"].count("?")==1)
historial += [{"role":"user","text":"Ahora hazme una pregunta para practicar lo que acabas de explicar y espera mi respuesta."},{"role":"assistant","text":quiz["answer"]}]
feedback = llamar("chat", {**contexto,"question":"Creo que reducir el ancho aumenta el contraste, pero también satura más intensidades. ¿Lo entendí bien?","language":"es","history":historial}).json()
registrar("El chat responde al siguiente turno con historial", len(feedback.get("answer",""))>30)
en = llamar("chat", {**contexto, "question":"Ahora explícame esta ventana en inglés, en dos frases.", "language":"es"}).json()
registrar("Solicitud explícita de inglés", bool(en.get("answer")) and en.get("language")=="en")
for nombre, texto, origen, destino in [("es",es["answer"],"es","es"),("en",en["answer"],"en","en"),("traduccion",en["answer"],"en","es")]:
    audio = llamar("speech", {"text":texto,"source_language":origen,"language":destino}).json()
    sonido = base64.b64decode(audio.get("audio", ""))
    registrar("MP3 real " + nombre, len(sonido)>1000 and audio.get("language")==destino)
    (ROOT / ".build" / ("smoke-" + nombre + ".mp3")).write_bytes(sonido)
registrar("Pregunta vacía rechazada", llamar("chat", {**contexto, "question":"", "language":"es"}).status_code==400)
# Importa únicamente seis cortes del fantoma público para comprobar todo el flujo de carga.
archivos = []
for ruta in (ROOT.parent / "dcm_qa_ct/In/Philips/S21570/S2020").iterdir():
    ds = pydicom.dcmread(ruta, stop_before_pixels=True)
    if "ImagePositionPatient" in ds:
        archivos.append((float(ds.ImagePositionPatient[2]), ruta))
archivos.sort()
buffer = io.BytesIO()
with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_dicom:
    for _, ruta in archivos[50:56]:
        zip_dicom.write(ruta, ruta.name)
permiso = llamar("upload-url", {}).json()
carga = sesion.post(permiso["upload"]["url"], data=permiso["upload"]["fields"], files={"file":("fantoma-prueba.zip",buffer.getvalue(),"application/zip")}, timeout=90)
registrar("Carga privada firmada de ZIP", carga.ok)
importado = llamar("import", {"key":permiso["key"]})
registrar("Importación DICOM real", importado.status_code==201 and importado.json()["shape"][0]==6)
registrar("Metadatos importados sin identificadores de paciente", all(k not in importado.json() for k in ["PatientName","PatientID","PatientBirthDate","InstitutionName"]))
(ROOT / ".build/smoke-result.json").write_text(json.dumps({"url":url,"checks":resultados,"spanish":es.get("answer"),"quiz":quiz.get("answer"),"feedback":feedback.get("answer"),"english":en.get("answer"),"imported_study":importado.json()["id"]},ensure_ascii=False,indent=2),encoding="utf-8")
print("Verificación completa:",len(resultados),"controles reales correctos.",flush=True)
