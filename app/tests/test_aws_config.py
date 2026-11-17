"""Comprueba la configuración de participantes sin consultar ni modificar AWS."""
import sys
from pathlib import Path

import pytest
from botocore.exceptions import ProfileNotFound

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import aws_config


def test_perfil_predeterminado_es_un_ejemplo_del_laboratorio(monkeypatch):
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setattr(aws_config, "configurar_tls", lambda: None)
    monkeypatch.setattr(aws_config.boto3, "Session", lambda **kwargs: kwargs)
    assert aws_config.crear_sesion() == {"profile_name": "sipaim-lab", "region_name": "us-east-1"}


def test_perfil_propio_se_respeta(monkeypatch):
    monkeypatch.setenv("AWS_PROFILE", "perfil-personal-del-asistente")
    monkeypatch.setattr(aws_config, "configurar_tls", lambda: None)
    monkeypatch.setattr(aws_config.boto3, "Session", lambda **kwargs: kwargs)
    assert aws_config.crear_sesion()["profile_name"] == "perfil-personal-del-asistente"


def test_perfil_inexistente_explica_como_prepararlo(monkeypatch):
    monkeypatch.setenv("AWS_PROFILE", "sipaim-lab")
    monkeypatch.setattr(aws_config, "configurar_tls", lambda: None)
    def ausente(**kwargs):
        raise ProfileNotFound(profile=kwargs["profile_name"])
    monkeypatch.setattr(aws_config.boto3, "Session", ausente)
    with pytest.raises(ValueError, match="aws configure sso --profile sipaim-lab"):
        aws_config.crear_sesion()


def test_nombre_propio_del_stack(monkeypatch):
    monkeypatch.setenv("AWS_STACK_NAME", "sipaim-lab-ana")
    assert aws_config.nombre_stack() == "sipaim-lab-ana"


@pytest.mark.parametrize("nombre", ["", "a", "NombreConMayusculas", "-invalido", "invalido-", "x" * 31])
def test_nombre_invalido_no_llega_a_aws(monkeypatch, nombre):
    monkeypatch.setenv("AWS_STACK_NAME", nombre)
    with pytest.raises(ValueError, match="AWS_STACK_NAME"):
        aws_config.nombre_stack()


def test_despliegue_incompleto_falla_antes_de_crear_recursos(tmp_path):
    with pytest.raises(ValueError, match="todavía no se han creado recursos AWS"):
        aws_config.validar_preparacion(tmp_path)


def test_preparacion_completa_se_acepta(tmp_path):
    for nombre in ("numpy", "pydicom", "PIL"):
        (tmp_path / ".build/package" / nombre).mkdir(parents=True)
    (tmp_path / "data").mkdir()
    (tmp_path / "data/manifest.json").write_text("[]")
    for estudio in ("head", "thorax", "phantom"):
        directorio = tmp_path / "data" / estudio
        directorio.mkdir()
        (directorio / "volume.npz").touch()
        (directorio / "metadata.json").write_text("{}")
    aws_config.validar_preparacion(tmp_path)
