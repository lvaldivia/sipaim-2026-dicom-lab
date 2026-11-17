"""Configura el perfil local sin guardar credenciales ni desactivar TLS."""
import os
import re
import ssl
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ProfileNotFound

PERFIL_PREDETERMINADO = "sipaim-lab"
REGION = "us-east-1"


def nombre_stack():
    nombre = os.environ.get("AWS_STACK_NAME", "sipaim-dicom-lab").strip()
    if not re.fullmatch(r"[a-z][a-z0-9-]{1,28}[a-z0-9]", nombre):
        raise ValueError("AWS_STACK_NAME debe tener entre 3 y 30 caracteres: minúsculas, números y guiones; comenzar con una letra y terminar con letra o número.")
    return nombre


def validar_preparacion(raiz_app):
    raiz_app = Path(raiz_app)
    necesarios = [raiz_app / ".build/package" / nombre for nombre in ("numpy", "pydicom", "PIL")]
    necesarios += [raiz_app / "data/manifest.json"]
    necesarios += [raiz_app / "data" / estudio / archivo for estudio in ("head", "thorax", "phantom") for archivo in ("volume.npz", "metadata.json")]
    faltantes = [str(p.relative_to(raiz_app)) for p in necesarios if not p.exists()]
    if faltantes:
        raise ValueError("Falta preparar el proyecto antes de desplegar: " + ", ".join(faltantes) + ". Siga los pasos de descarga, prepare_data.py y dependencias Linux del README; todavía no se han creado recursos AWS.")


def configurar_tls():
    if os.environ.get("AWS_CA_BUNDLE") or sys.platform != "win32":
        return
    # Windows puede confiar en certificados corporativos ausentes del bundle de botocore.
    destino = Path(__file__).resolve().parents[1] / ".local/aws-windows-ca.pem"
    destino.parent.mkdir(exist_ok=True)
    certificados = []
    for almacen in ("ROOT", "CA"):
        for certificado, codificacion, _ in ssl.enum_certificates(almacen):
            if codificacion == "x509_asn":
                certificados.append(ssl.DER_cert_to_PEM_cert(certificado))
    destino.write_text("".join(certificados), encoding="ascii")
    os.environ["AWS_CA_BUNDLE"] = str(destino)


def crear_sesion():
    configurar_tls()
    perfil = os.environ.get("AWS_PROFILE", PERFIL_PREDETERMINADO).strip()
    if not perfil:
        raise ValueError("AWS_PROFILE está vacío. Seleccione el perfil del laboratorio, por ejemplo sipaim-lab.")
    try:
        return boto3.Session(profile_name=perfil, region_name=REGION)
    except ProfileNotFound as error:
        raise ValueError(f"No existe el perfil AWS '{perfil}'. Cree su propio perfil con 'aws configure sso --profile {perfil}' o 'aws configure --profile {perfil}' y verifique su cuenta antes de continuar.") from error
