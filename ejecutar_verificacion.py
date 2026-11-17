"""Ejecuta las celdas científicas con datos reales y backend estático local.

Las diferencias respecto a Colab se documentan en verificacion_ejecucion.json.
"""
import contextlib
import json
import time
import traceback
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from IPython.display import display

notebook = json.loads(Path("SIPAIM_2026_DICOM_Python.ipynb").read_text(encoding="utf-8"))
estado = {"display": display, "__name__": "__verificacion__"}
reporte = {"entorno": "Python local Windows, CPU", "adaptaciones": ["Bibliotecas instaladas en .venv; no se ejecuta %pip de Colab", "Datos A y B ya descargados por los comandos reales", "Plotly.show sustituido por write_html para evitar abrir navegadores", "Matplotlib usa Agg; PNG verificados por separado", "Drive e IDC opcional desactivados como en el notebook"], "celdas": []}
numero_plotly = 0
Path("verificacion_visual").mkdir(exist_ok=True)

def guardar_plotly(figura, *args, **kwargs):
    global numero_plotly
    numero_plotly += 1
    figura.write_html(f"verificacion_visual/plotly_{numero_plotly}.html", include_plotlyjs=True)

go.Figure.show = guardar_plotly
inicio = time.time()
with Path("verificacion_ejecucion.log").open("w", encoding="utf-8") as log:
    with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        for indice, celda in enumerate(notebook["cells"]):
            if celda["cell_type"] != "code":
                continue
            fuente = "".join(celda["source"])
            entrada = {"indice": indice, "id": celda["id"]}
            if "%pip" in fuente or 'subprocess.run(["git"' in fuente or "cliente_torax.download_from_selection" in fuente:
                entrada["resultado"] = "preparación ya realizada"
                reporte["celdas"].append(entrada)
                continue
            print(f"\nCELDA {indice}: {celda['id']}", flush=True)
            try:
                exec(compile(fuente, f"celda_{indice}", "exec"), estado)
                entrada["resultado"] = "correcto"
                plt.close("all")
            except Exception:
                entrada["resultado"] = "error"
                entrada["detalle"] = traceback.format_exc()
                print(entrada["detalle"], flush=True)
                reporte["celdas"].append(entrada)
                break
            reporte["celdas"].append(entrada)
        if not any(c["resultado"] == "error" for c in reporte["celdas"]):
            for nombre, arreglo in [("cerebro", estado["hu_craneo"]), ("pulmones", estado["hu_torax_central"])]:
                nivel, ancho = (40, 80) if nombre == "cerebro" else (-600, 1500)
                plt.imsave(f"verificacion_visual/{nombre}.png", estado["ventana"](arreglo, nivel, ancho), cmap="gray", vmin=0, vmax=1)
reporte["segundos"] = round(time.time() - inicio, 2)
Path("verificacion_ejecucion.json").write_text(json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8")
errores = [c for c in reporte["celdas"] if c["resultado"] == "error"]
print(f"Celdas revisadas: {len(reporte['celdas'])}. Errores: {len(errores)}. Duración: {reporte['segundos']} s.")
if errores:
    print(errores[0]["detalle"])
    raise SystemExit(1)
