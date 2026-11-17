from pathlib import Path
from idc_index import IDCClient

cliente = IDCClient.client()
uid = "1.3.6.1.4.1.14519.5.2.1.6279.6001.100225287222365663678666836860"
seleccion = cliente.sql_query(f"SELECT * FROM index WHERE SeriesInstanceUID = '{uid}'")
print(seleccion.to_string(index=False))
seleccion.to_json("lidc_seleccion.json", orient="records", indent=2)
destino = Path("torax_lidc")
destino.mkdir(exist_ok=True)
cliente.download_from_selection(downloadDir=str(destino.resolve()), seriesInstanceUID=uid)
print("Archivos recibidos:", sum(p.is_file() for p in destino.rglob("*")))
