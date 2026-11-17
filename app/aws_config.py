"""Configura el perfil local sin guardar credenciales ni desactivar TLS."""
import os
import ssl
import sys
from pathlib import Path

import boto3


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
    return boto3.Session(profile_name=os.environ.get("AWS_PROFILE", "luisvaldivia"), region_name="us-east-1")
