"""Genera el material de SIPAIM en formato Jupyter sin dependencias externas."""
import json
import textwrap
from pathlib import Path

cells = []


def md(text):
    cells.append(dict(cell_type="markdown", metadata={}, source=textwrap.dedent(text).strip() + "\n"))


def code(explanation, source):
    md(explanation)
    cells.append(dict(cell_type="code", execution_count=None, metadata={}, outputs=[], source=textwrap.dedent(source).strip() + "\n"))


md('''
# Explorando imágenes médicas con DICOM: introducción práctica con Python
**SIPAIM 2026 · Taller práctico · Material en español**

> **Aviso: este material es educativo y no sirve para diagnóstico clínico.**

Dirigido a investigadores, ingenieros biomédicos, médicos y estudiantes con conocimientos básicos de Python y sin experiencia previa con DICOM. Trabajaremos en **Google Colab, con CPU y sin GPU**. Ejecute las celdas en orden. Los ejercicios y sus soluciones son independientes; los bonus se pueden explorar al terminar.

Al finalizar podrá inspeccionar metadatos, interpretar píxeles CT en unidades Hounsfield, elegir ventanas, construir un volumen y generar reconstrucciones y superficies tridimensionales.

## Índice
- [0 · Preparación](#preparacion)
- [Parte 1 · Fundamentos del estándar DICOM](#parte1)
- [Parte 2 · Lectura de DICOM con pydicom](#parte2)
- [Parte 3 · Procesamiento de imágenes CT](#parte3)
- [Parte 4 · Reconstrucción y visualización 3D](#parte4)
- [Conclusiones · Un pequeño pipeline de investigación](#conclusiones)
- [Recursos, créditos y licencias](#recursos)
- [Exportar figuras para las diapositivas](#figuras-ppt)
''')
md('''
<a id="preparacion"></a>
## 0 · Preparación
Seleccione un entorno de ejecución de Colab con CPU. Instalaremos exclusivamente las bibliotecas científicas indicadas; `pathlib`, `subprocess` y `copy` pertenecen a Python. Los módulos de Google Colab se usan solamente para su integración con Drive y widgets.

Todos los datos se obtienen aquí, antes del análisis. El cráneo humano GE y el fantoma Philips proceden de [dcm_qa_ct](https://github.com/neurolabusc/dcm_qa_ct). Para los pulmones usamos una CT torácica de [LIDC-IDRI](https://portal.imaging.datacommons.cancer.gov/collections/lidc_idri/), descargada mediante IDC. No se necesita cuenta ni credencial para estas descargas.

**Respaldo antes del evento:** copie las carpetas `dcm_qa_ct` (con las dos subcarpetas seleccionadas) y `torax_lidc` (con la serie ya descargada) a `Mi unidad/SIPAIM_DICOM/` en Drive. Si la red de los repositorios falla, active `USAR_DRIVE` en la celda de respaldo y continúe con la verificación. Drive también requiere conectividad; no sustituye un respaldo local cuando no hay Internet en absoluto.
''')
code('''### Instalar las bibliotecas
Instalamos las herramientas de lectura, cálculo y visualización. Se espera una instalación sin errores; no se añaden decodificadores ni motores de exportación. Colab ya proporciona varias de estas bibliotecas.''', '''
# Instala las bibliotecas del taller en el entorno activo de Colab.
%pip -q install pydicom numpy pandas matplotlib scikit-image scipy SimpleITK plotly ipywidgets idc-index
''')
code('''### Importar y definir las rutas
Centralizamos los nombres de las carpetas para que el respaldo use exactamente el mismo análisis. Se espera imprimir el directorio de trabajo.''', '''
from pathlib import Path  # Manipula rutas sin depender del sistema operativo.
import subprocess  # Ejecuta git, wget y unzip disponibles en Colab.
import copy  # Permite modificar una copia del Dataset.
import pydicom  # Lee y escribe archivos DICOM.
import numpy as np  # Opera sobre matrices y volúmenes.
import pandas as pd  # Presenta tablas de metadatos.
import matplotlib.pyplot as plt  # Dibuja figuras estáticas y exporta PNG.
from skimage import measure, morphology  # Etiqueta componentes y extrae superficies.
from scipy import ndimage  # Suaviza y rellena máscaras binarias.
import SimpleITK as sitk  # Convierte series a NIfTI conservando geometría.
import plotly.graph_objects as go  # Muestra mallas interactivas.
import ipywidgets as widgets  # Añade controles interactivos.
BASE = Path.cwd()  # Usa el directorio de trabajo actual.
REPO = BASE / "dcm_qa_ct"  # Define el repositorio de cráneo.
CARPETA_GE = REPO / "In/GE"  # Localiza la serie humana GE.
CARPETA_PHILIPS = REPO / "In/Philips/S21570/S2020"  # Localiza el fantoma elegido.
CARPETA_TORAX = BASE / "torax_lidc"  # Localiza la CT torácica elegida de LIDC-IDRI.
UID_TORAX = "1.3.6.1.4.1.14519.5.2.1.6279.6001.100225287222365663678666836860"  # Fija una única serie para que todos trabajemos con los mismos datos.
print("Directorio de trabajo:", BASE)  # Confirma dónde se guardarán los datos.
''')
code('''### A · Descargar únicamente las series de cráneo necesarias
El *sparse checkout* evita descargar las demás series. Los comandos equivalen a los indicados por el repositorio; si ya existe una copia, se reutiliza. Se espera disponer de `In/GE` y `In/Philips/S21570/S2020`. Un fallo de red se informa sin impedir activar el respaldo.''', '''
try:  # Captura fallos de red para permitir el respaldo.
    if not REPO.exists():  # Evita clonar nuevamente en una carpeta existente.
        subprocess.run(["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", "https://github.com/neurolabusc/dcm_qa_ct"], check=True, timeout=240)  # Clona sin cargar todos los blobs.
    subprocess.run(["git", "sparse-checkout", "set", "In/GE", "In/Philips/S21570/S2020"], cwd=REPO, check=True, timeout=240)  # Selecciona solo las series requeridas.
    print("Descarga A disponible; se verificará abajo.")  # Anuncia el siguiente control.
except (subprocess.SubprocessError, OSError) as error:  # Reconoce fallos del comando o de conexión.
    print("No se completó A. Active el respaldo de Drive. Detalle:", error)  # Explica la alternativa.
''')
code('''### B · Descargar una CT de tórax de LIDC-IDRI
Descargamos una sola serie torácica por su UID mediante `idc-index`; no se descarga la colección completa. Se trata de **LIDC-IDRI-1001**, con **194 cortes**, aproximadamente **102 MB**, equipo Siemens Sensation 16. Consultamos primero sus metadatos para mostrar paciente seudonimizado, número esperado de instancias y tamaño. Después comprobaremos los archivos recibidos. La licencia de los datos es CC BY 3.0; el crédito completo figura al final.''', '''
try:  # Permite continuar hacia el respaldo si falla la descarga.
    from idc_index import IDCClient  # Importa el cliente de descarga oficial de IDC.
    cliente_torax = IDCClient.client() if hasattr(IDCClient, "client") else IDCClient()  # Crea el cliente compatible con la versión instalada.
    consulta_torax = f"SELECT PatientID, SeriesInstanceUID, instanceCount, series_size_MB FROM index WHERE SeriesInstanceUID = '{UID_TORAX}'"  # Consulta exclusivamente la serie fijada para el taller.
    ficha_torax = cliente_torax.sql_query(consulta_torax)  # Recupera el recuento y tamaño publicados en el índice.
    print(ficha_torax.to_string(index=False))  # Presenta la selección antes de descargar.
    assert len(ficha_torax) == 1, "La serie seleccionada no está disponible en este índice."  # Impide una descarga sin filtro válido.
    CARPETA_TORAX.mkdir(exist_ok=True)  # Crea un destino separado de otros estudios.
    cliente_torax.download_from_selection(downloadDir=str(CARPETA_TORAX), seriesInstanceUID=UID_TORAX)  # Descarga únicamente los cortes de esta serie.
    print("Descarga B disponible; se verificará abajo.")  # Anuncia la búsqueda recursiva.
except Exception as error:  # Captura problemas de red o disponibilidad del servicio.
    print("No se completó B. Active el respaldo de Drive. Detalle:", error)  # Indica cómo recuperar los datos.
''')
code('''### D · Respaldo desde Google Drive
Esta celda no hace nada si `USAR_DRIVE=False`, de modo que «Ejecutar todas» no solicita autorización. Si necesita el respaldo, cambie a `True` y ejecute esta celda **antes de verificar los archivos**. Se espera encontrar `SIPAIM_DICOM/dcm_qa_ct/In/...` y `SIPAIM_DICOM/torax_lidc/...`; las rutas de lectura se redirigen a Drive.''', '''
USAR_DRIVE = False  # Cambie a True solamente para usar el respaldo preparado.
if USAR_DRIVE:  # Evita montar Drive durante la ejecución normal.
    from google.colab import drive  # Importa la integración propia de Colab.
    drive.mount("/content/drive")  # Solicita acceso a su unidad de Google Drive.
    RESPALDO = Path("/content/drive/MyDrive/SIPAIM_DICOM")  # Señala la carpeta preparada por el ponente.
    CARPETA_GE = RESPALDO / "dcm_qa_ct/In/GE"  # Redirige la lectura del cráneo humano.
    CARPETA_PHILIPS = RESPALDO / "dcm_qa_ct/In/Philips/S21570/S2020"  # Redirige la lectura del fantoma.
    CARPETA_TORAX = RESPALDO / "torax_lidc"  # Redirige la lectura de la serie torácica preparada.
    print("Respaldo activado:", RESPALDO)  # Confirma la selección.
else:  # Mantiene las rutas descargadas cuando hay conexión.
    print("Se usarán los datos descargados en Colab.")  # Confirma el modo normal.
''')
code('''### Verificar archivos y geometría inicial
GE usa extensión `.dcm`; Philips tiene nombres como `I1180`, sin extensión. Para Philips y tórax examinamos **todos** los archivos, rechazamos objetos sin posición o sin píxeles decodificables y ordenamos por z. `force=True` permite leer DICOM sin preámbulo, pero no convierte un archivo arbitrario en una imagen válida. Se esperan 28 cortes GE y series Philips y LIDC-IDRI no vacías. Veremos también espaciado y grosor; no son conceptos equivalentes.''', '''
archivos_ge = sorted(CARPETA_GE.glob("*.dcm"))  # Enumera únicamente los DICOM GE.
archivo_referencia = CARPETA_GE / "18.dcm"  # Fija el archivo de referencia para todo el análisis 2D.
series_iniciales = {}  # Conserva los cortes válidos de Philips y tórax.
for nombre, carpeta in [("Philips", CARPETA_PHILIPS), ("Tórax", CARPETA_TORAX)]:  # Revisa ambas fuentes.
    archivos = sorted(p for p in carpeta.rglob("*") if p.is_file())  # Busca archivos sin exigir extensión.
    cortes = []  # Acumula los Datasets válidos.
    descartados = 0  # Cuenta los archivos no utilizables.
    for ruta in archivos:  # Examina individualmente cada archivo encontrado.
        try:  # Tolera archivos auxiliares dentro de las carpetas.
            candidato = pydicom.dcmread(ruta, force=True)  # Lee incluso si falta el preámbulo DICOM.
            if "ImagePositionPatient" not in candidato:  # Exige posición para construir el volumen.
                descartados += 1  # Registra el descarte por falta de posición.
                continue  # Pasa al siguiente archivo.
            pixeles = candidato.pixel_array  # Comprueba que los píxeles se pueden decodificar.
            if pixeles.ndim != 2:  # Limita el taller a cortes monocromos de una sola imagen.
                descartados += 1  # Registra objetos fuera del alcance del ejemplo.
                continue  # Omite objetos multiframe o de color.
            cortes.append(candidato)  # Conserva el corte válido.
        except Exception:  # Los archivos no DICOM o sin decodificador no son cortes válidos.
            descartados += 1  # Registra el archivo descartado.
    cortes.sort(key=lambda corte: float(corte.ImagePositionPatient[2]))  # Ordena de inferior a superior.
    series_iniciales[nombre] = cortes  # Guarda los cortes para el análisis posterior.
    print(nombre, "— archivos:", len(archivos), "cortes válidos:", len(cortes), "descartados:", descartados)  # Informa el resultado real.
    if cortes:  # Consulta geometría solo cuando hay imágenes válidas.
        print("PixelSpacing:", cortes[0].get("PixelSpacing"), "SliceThickness:", cortes[0].get("SliceThickness"))  # Muestra los valores del primer corte.
print("GE — archivos .dcm:", len(archivos_ge))  # Verifica el número de cortes humanos.
assert len(archivos_ge) == 28 and archivo_referencia.exists(), "Falta GE: revise la descarga o active Drive."  # Detiene un análisis con datos incompletos.
assert len(series_iniciales["Philips"]) > 1, "Falta Philips: revise la descarga o active Drive."  # Exige un volumen de fantoma.
assert len(series_iniciales["Tórax"]) == 194, "Se esperan 194 cortes LIDC-IDRI; revise descarga o respaldo."  # Detecta una descarga ausente o incompleta incluso desde Drive.
assert all(str(c.SeriesInstanceUID) == UID_TORAX for c in series_iniciales["Tórax"]), "La carpeta contiene otra serie torácica."  # Impide mezclar el estudio anterior con el nuevo.
if "ficha_torax" in globals() and len(ficha_torax) == 1:  # Usa el índice para comprobar la integridad de la descarga.
    assert len(series_iniciales["Tórax"]) == int(ficha_torax.iloc[0]["instanceCount"]), "El número de cortes no coincide con el índice IDC."  # Detecta una descarga incompleta.
cortes_torax = series_iniciales["Tórax"]  # Da un nombre breve al torso ordenado.
''')
code('''### C · Opcional: para practicar en casa con IDC
La descarga opcional queda desactivada para no depender de otro servicio durante la charla. Active `PRACTICAR_IDC` para consultar el índice SQL por CT de tórax de 100 a 300 instancias, ordenar por tamaño y descargar solo la primera serie mediante `download_from_selection`. Se espera una tabla y el recuento de archivos descargados; si falla la red, se informa y el taller principal continúa. Revise las condiciones y la cita de la colección elegida.''', '''
PRACTICAR_IDC = False  # Active esta opción al practicar fuera de la sesión.
if PRACTICAR_IDC:  # Mantiene la actividad principal independiente de IDC.
    try:  # Protege frente a fallos de red o cambios del servicio.
        from idc_index import IDCClient  # Importa el cliente oficial de IDC.
        cliente = IDCClient.client() if hasattr(IDCClient, "client") else IDCClient()  # Admite la fábrica actual y versiones anteriores.
        consulta = "SELECT SeriesInstanceUID, collection_id, instanceCount, series_size_MB FROM index WHERE Modality = 'CT' AND BodyPartExamined = 'CHEST' AND instanceCount BETWEEN 100 AND 300 ORDER BY series_size_MB ASC, SeriesInstanceUID ASC LIMIT 1"  # Define una consulta acotada y reproducible en cada versión del índice.
        seleccion = cliente.sql_query(consulta)  # Consulta el índice local del cliente.
        print(seleccion.to_string(index=False))  # Presenta la primera serie elegible.
        if not seleccion.empty:  # Evita descargar sin un filtro de serie válido.
            carpeta_idc = BASE / "idc_casa"  # Define un destino separado de A y B.
            carpeta_idc.mkdir(exist_ok=True)  # Crea el destino requerido por el cliente.
            uid_idc = str(seleccion.iloc[0]["SeriesInstanceUID"])  # Extrae únicamente el identificador de la primera serie.
            cliente.download_from_selection(downloadDir=str(carpeta_idc), seriesInstanceUID=uid_idc)  # Descarga solo la selección.
            print("Archivos IDC recibidos:", sum(p.is_file() for p in carpeta_idc.rglob("*")))  # Verifica cuántos archivos llegaron.
        else:  # Contempla un índice sin coincidencias.
            print("No se encontraron series con esos criterios.")  # Explica la ausencia de descarga.
    except Exception as error:  # Mantiene el material principal operativo si IDC falla.
        print("IDC no está disponible; revise la conexión y vuelva a intentarlo en casa. Detalle:", error)  # Informa el fallo con claridad.
else:  # Informa que no hay una descarga pendiente.
    print("IDC opcional desactivado; A y B bastan para todo el taller.")  # Confirma la independencia de los datos principales.
''')
md('''
<a id="parte1"></a>
## Parte 1 · Fundamentos del estándar DICOM
**DICOM** (*Digital Imaging and Communications in Medicine*) es un estándar para representar, intercambiar y gestionar imágenes médicas y su información asociada. No es solamente una extensión de archivo: también define servicios de comunicación.

Un objeto de imagen contiene atributos de identificación, adquisición y geometría, que llamaremos **header**, y datos de imagen en **Pixel Data (7FE0,0010)**. Pixel Data también es un elemento DICOM; no todos los objetos DICOM contienen una imagen. Cada elemento tiene una dirección `(grupo, elemento)`, una representación de valor (VR) y un valor.

La jerarquía habitual es **Paciente → Estudio → Serie → Instancia**. Un estudio agrupa una exploración; una serie reúne imágenes adquiridas o reconstruidas con un contexto común. Un corte clásico suele ser una instancia, mientras que un objeto multiframe puede contener muchos cortes. Los UID identifican estudios, series e instancias.

Modalidades frecuentes: **CT** (tomografía computarizada), **MR** (resonancia magnética), **US** (ecografía), **PT** (PET) y **CR/DX** (radiografía). Un visor es adecuado para inspección visual; el código facilita mediciones repetibles, procesamiento masivo, control de calidad y experimentos reproducibles.

### Identificación y privacidad
Que un tag exista no significa que contenga un identificador real: puede estar vacío o reemplazado. Aun así, hay que revisar los atributos, sus secuencias, tags privados y posibles textos incrustados en los píxeles. Una lista corta de atributos nunca demuestra anonimización completa.
''')
code('''### Inspeccionar posibles identificadores en `18.dcm`
Leemos exclusivamente el archivo de referencia y mostramos la presencia y el contenido de cinco tags de PHI (*Protected Health Information*). También contamos tags privados, incluidos los anidados. Se espera reconocer qué campos están presentes, vacíos o ausentes; no se infiere identidad a partir de sus valores.''', '''
ds = pydicom.dcmread(archivo_referencia)  # Lee el cráneo GE fijado como referencia.
tags_phi = ["PatientName", "PatientID", "PatientBirthDate", "InstitutionName", "ReferringPhysicianName"]  # Define atributos de identificación a revisar.
tabla_phi = pd.DataFrame([{"Tag": nombre, "Presente": nombre in ds, "Valor": str(ds.get(nombre, "<ausente>"))} for nombre in tags_phi])  # Distingue ausencia de valor vacío.
print(tabla_phi.to_string(index=False))  # Presenta la inspección de PHI.
privados = [elemento for elemento in ds.iterall() if elemento.tag.is_private]  # Incluye elementos privados dentro de secuencias.
print("¿Existen tags privados?", bool(privados), "Cantidad:", len(privados))  # Informa su presencia sin atribuirles un significado.
''')
md('''
<a id="parte2"></a>
## Parte 2 · Lectura de DICOM con pydicom
`pydicom` representa un archivo como un `Dataset`: una colección de elementos DICOM. Primero exploraremos su contenido; después separaremos metadatos y matriz de píxeles. En esta parte el cráneo de referencia será **siempre `In/GE/18.dcm`**.
''')
code('''### 2.1 · Leer e imprimir el Dataset completo
Volvemos a leer `18.dcm` para hacer explícita la operación básica. La salida será extensa: busque modalidad, geometría, calibración y Pixel Data. La impresión de Pixel Data resume el bloque binario, no muestra la imagen.''', '''
ds = pydicom.dcmread(archivo_referencia)  # Lee nuevamente el archivo de referencia 18.dcm.
print(ds)  # Imprime todos los elementos del Dataset, incluidas las secuencias.
''')
code('''### 2.2 · Acceder por nombre, dirección y `get`
Comparamos tres accesos a la modalidad. Por dirección obtenemos un `DataElement`, cuyo `.value` contiene el valor; por nombre obtenemos el valor directamente. `ds.get()` permite definir un resultado para atributos ausentes. Se espera `CT` en los tres accesos.''', '''
print("Por nombre:", ds.Modality)  # Consulta un atributo mediante su palabra clave.
print("Por dirección:", ds[(0x0008, 0x0060)].value)  # Accede al valor de Modality mediante grupo y elemento.
print("Con get:", ds.get("Modality", "No disponible"))  # Proporciona un valor alternativo seguro.
print("Campo posiblemente ausente:", ds.get("PatientComments", "No disponible"))  # Demuestra el acceso tolerante a campos opcionales.
''')
code('''### 2.3 · Construir una tabla de metadatos clave
Reunimos atributos que vinculan imagen, equipo, posición y calibración. Se esperan CT, HEAD, matriz 512 × 512, grosor 7 mm y gantry inclinado aproximadamente +18,5°. `PixelSpacing` tiene orden **fila, columna**, en mm. `SliceThickness` describe el grosor reconstruido, no garantiza la distancia entre centros de cortes.''', '''
tags_clave = ["Modality", "BodyPartExamined", "Manufacturer", "Rows", "Columns", "PixelSpacing", "SliceThickness", "ImagePositionPatient", "RescaleSlope", "RescaleIntercept", "GantryDetectorTilt"]  # Define los atributos del análisis.
tabla_ge = pd.DataFrame({"Tag": tags_clave, "GE · 18.dcm": [str(ds.get(tag, "<ausente>")) for tag in tags_clave]})  # Convierte valores heterogéneos a texto legible.
print(tabla_ge.to_string(index=False))  # Muestra la tabla completa.
assert ds.Modality == "CT" and ds.BodyPartExamined == "HEAD", "El archivo no coincide con el cráneo esperado."  # Verifica modalidad y región.
assert int(ds.Rows) == 512 and int(ds.Columns) == 512 and float(ds.SliceThickness) == 7.0, "Revise el archivo de referencia."  # Comprueba dimensiones y grosor.
''')
code('''### 2.4 · Visualizar los píxeles almacenados con escala mín–máx
`pixel_array` decodifica la matriz; todavía no aplica la calibración a HU. Se esperan mínimo −1500 y máximo 1698. La visualización puede parecer «lavada»: un rango amplio dedica gran parte de los grises al aire y hueso, dejando poco contraste para diferencias sutiles del cerebro. No es un problema de resolución ni se corrige cambiando los datos originales.''', '''
crudo = ds.pixel_array  # Decodifica los valores almacenados en 18.dcm.
print("Forma:", crudo.shape, "Tipo:", crudo.dtype, "Mínimo:", crudo.min(), "Máximo:", crudo.max())  # Describe la matriz original.
assert crudo.min() == -1500 and crudo.max() == 1698, "Los píxeles no coinciden con 18.dcm."  # Verifica los valores conocidos.
fig_crudo, ax = plt.subplots(figsize=(6, 6))  # Crea una figura para inspección y exportación.
ax.imshow(crudo, cmap="gray", vmin=crudo.min(), vmax=crudo.max())  # Distribuye los grises entre mínimo y máximo.
ax.set_title("GE · 18.dcm · valores almacenados")  # Identifica el archivo y la escala.
ax.axis("off")  # Oculta índices que no representan coordenadas físicas.
plt.show()  # Presenta la figura.
''')
code('''### 2.5 · Comparar con el primer corte del tórax
Tomamos el primer corte por posición z, sin asumir su nombre. Comparamos exactamente los mismos tags. Se espera observar diferencias de equipo, región, espaciado o calibración, y posiblemente atributos ausentes: nunca debemos copiar constantes de un estudio a otro.''', '''
ds_torax = cortes_torax[0]  # Selecciona el corte más inferior del torso.
tabla_comparada = tabla_ge.copy()  # Conserva la columna del cráneo.
tabla_comparada["Tórax · primer corte"] = [str(ds_torax.get(tag, "<ausente>")) for tag in tags_clave]  # Añade los mismos atributos del torso.
print(tabla_comparada.to_string(index=False))  # Facilita la comparación entre adquisiciones.
''')
md('''
### Ejercicio 1 · Interpretar metadatos
Con `18.dcm` y la carpeta GE, determine:
1. Modalidad y región del cuerpo.
2. Ancho y alto del campo de visión en mm: `Columns × PixelSpacing[1]` y `Rows × PixelSpacing[0]`.
3. Número de archivos de la serie GE.
4. Tags que podrían identificar al paciente o al centro.

Use los atributos ya explorados. El producto tamaño × espaciado representa la extensión de los píxeles; la distancia entre los centros extremos sería `(tamaño − 1) × espaciado`.
''')
code('''### Solución · Ejercicio 1
Calculamos la extensión física y recuperamos la identificación potencial. Se espera CT, HEAD, aproximadamente 250 mm por lado y 28 archivos. El conjunto de cinco tags es ilustrativo, no un protocolo de desidentificación.''', '''
print("Modalidad:", ds.Modality, "Región:", ds.BodyPartExamined)  # Responde la modalidad y región del cráneo.
ancho_mm = int(ds.Columns) * float(ds.PixelSpacing[1])  # Multiplica columnas por espaciado horizontal.
alto_mm = int(ds.Rows) * float(ds.PixelSpacing[0])  # Multiplica filas por espaciado vertical.
print(f"Campo de visión: {ancho_mm:.2f} × {alto_mm:.2f} mm")  # Expresa el tamaño físico en milímetros.
print("Archivos GE:", len(archivos_ge))  # Informa los 28 archivos descargados.
print("Revisar:", ", ".join(tags_phi), "y otros identificadores, UID, fechas, secuencias y píxeles.")  # Amplía la revisión de privacidad.
''')
md('''
<a id="parte3"></a>
## Parte 3 · Procesamiento de imágenes CT
Los valores almacenados dependen de la representación del fabricante. En estos CT convencionales, **HU = valor almacenado × RescaleSlope + RescaleIntercept**. El aire suele estar alrededor de −1000 HU y el agua alrededor de 0 HU; los tejidos blandos ocupan rangos próximos a estos valores y el hueso puede superar ampliamente +300 HU. Los rangos dependen de adquisición, reconstrucción y material: son referencias, no etiquetas diagnósticas.
''')
code('''### 3.1 · Calibrar a HU y comprobar dos regiones
Convertimos a `float32` antes de multiplicar para evitar desbordamientos. En una esquina puede haber aire o relleno fuera del campo reconstruido; excluimos `PixelPaddingValue` cuando está definido. La región ósea se selecciona por umbral para una comprobación ilustrativa, no como medición independiente. Se esperan valores negativos de aire y positivos altos en el hueso; mostraremos ambas regiones sobre `18.dcm`.''', '''
hu_craneo = crudo.astype(np.float32) * float(ds.RescaleSlope) + float(ds.RescaleIntercept)  # Aplica la calibración del propio archivo.
valido = np.ones(crudo.shape, dtype=bool)  # Inicializa una máscara de píxeles utilizables.
if "PixelPaddingValue" in ds:  # Evita medir valores de relleno como si fueran tejido.
    limite_padding = float(ds.get("PixelPaddingRangeLimit", ds.PixelPaddingValue))  # Recupera el extremo del rango de relleno.
    minimo_padding, maximo_padding = sorted([float(ds.PixelPaddingValue), limite_padding])  # Ordena los límites del relleno.
    valido &= ~((crudo >= minimo_padding) & (crudo <= maximo_padding))  # Excluye el valor o rango de padding.
roi_esquina = hu_craneo[:64, :64]  # Define una región en la esquina superior izquierda.
aire_esquina = roi_esquina[valido[:64, :64] & (roi_esquina > -1100) & (roi_esquina < -800)]  # Selecciona candidatos de aire físico dentro de la esquina.
mascara_hueso = (hu_craneo > 700) & (hu_craneo < 2000) & valido  # Selecciona píxeles compatibles con hueso del cráneo.
print("Pendiente:", ds.RescaleSlope, "Intercepto:", ds.RescaleIntercept)  # Explicita la transformación aplicada.
print("Esquina completa, mediana HU:", float(np.median(roi_esquina)))  # Permite detectar relleno en la esquina.
print("Aire en esquina, mediana HU:", float(np.median(aire_esquina)) if aire_esquina.size else "Sin aire válido: la esquina contiene relleno; no interpretarlo como aire.")  # Evita una medición engañosa del padding.
print("Hueso seleccionado, mediana HU:", float(np.median(hu_craneo[mascara_hueso])) if mascara_hueso.any() else "Sin píxeles óseos seleccionados")  # Comprueba la escala positiva del hueso.
fig, ax = plt.subplots(figsize=(6, 6))  # Crea un control visual de las regiones.
ax.imshow(hu_craneo, cmap="gray", vmin=-1000, vmax=1500)  # Muestra el cráneo en una escala amplia de HU.
ax.contour(mascara_hueso, levels=[0.5], colors="orange", linewidths=0.3)  # Delimita la selección ósea para inspección.
ax.plot([0, 63, 63, 0, 0], [0, 0, 63, 63, 0], color="cyan")  # Delimita la esquina usada para aire.
ax.set_title("Cian: esquina · Naranja: selección ósea")  # Explica las marcas superpuestas.
ax.axis("off")  # Oculta los índices de matriz.
plt.show()  # Presenta la comprobación visual.
''')
code('''### 3.2 · Histograma de HU de los 28 cortes GE
Calibramos cada corte con sus propios parámetros y acumulamos frecuencias en intervalos de 100 HU, sin construir un volumen regular de GE. Excluimos padding declarado y contabilizamos valores fuera de [−1100, 3000] HU. Se espera un pico de aire alrededor de −1000, tejido blando entre 0 y +100 y una cola de hueso. La mezcla de tejidos y los cortes afectan la forma del histograma.''', '''
bordes_hu = np.arange(-1100, 3100, 100)  # Define intervalos de 100 HU hasta 3000 HU.
hist_ge = np.zeros(len(bordes_hu) - 1, dtype=np.int64)  # Inicializa el acumulador de frecuencias.
fuera_ge = 0  # Cuenta valores fuera del rango representado.
for ruta in archivos_ge:  # Incluye los 28 cortes de cráneo GE.
    corte = pydicom.dcmread(ruta)  # Lee los parámetros propios del corte.
    matriz = corte.pixel_array  # Recupera los valores almacenados.
    valores = matriz.astype(np.float32) * float(corte.RescaleSlope) + float(corte.RescaleIntercept)  # Convierte a HU por corte.
    utilizables = np.ones(matriz.shape, dtype=bool)  # Inicializa la selección de píxeles.
    if "PixelPaddingValue" in corte:  # Excluye el padding declarado por el archivo.
        extremos = sorted([float(corte.PixelPaddingValue), float(corte.get("PixelPaddingRangeLimit", corte.PixelPaddingValue))])  # Determina el rango de relleno.
        utilizables &= ~((matriz >= extremos[0]) & (matriz <= extremos[1]))  # Omite valores sin significado físico.
    valores = valores[utilizables]  # Conserva únicamente valores válidos.
    hist_ge += np.histogram(valores, bins=bordes_hu)[0]  # Acumula el histograma del corte.
    fuera_ge += np.count_nonzero((valores < bordes_hu[0]) | (valores > bordes_hu[-1]))  # Registra valores no representados.
fig, ax = plt.subplots(figsize=(10, 4))  # Crea el histograma agregado.
ax.bar(bordes_hu[:-1], hist_ge, width=100, align="edge", color="steelblue")  # Dibuja un bloque por intervalo de HU.
ax.set(xlabel="HU", ylabel="Número de píxeles", title="GE · 28 cortes · intervalos de 100 HU")  # Identifica unidades y población.
plt.show()  # Presenta aire, tejidos blandos y cola ósea.
print("Valores válidos fuera del rango mostrado:", fuera_ge)  # Evita ocultar recortes del histograma.
''')
code('''### 3.3 · Histograma del tórax y comparación
Procesamos el torso con la misma calibración por corte y los mismos intervalos. Normalizamos por el total representado para comparar series con distinto número de píxeles. Se espera una contribución de pulmón aproximadamente entre −900 y −500 HU; el aire exterior también contribuye al extremo cercano a −1000 HU.''', '''
hist_torax = np.zeros_like(hist_ge)  # Inicializa frecuencias de tórax.
fuera_torax = 0  # Inicializa el control de valores no mostrados.
for corte in cortes_torax:  # Recorre los cortes válidos de la serie torácica.
    matriz = corte.pixel_array  # Recupera los píxeles originales del corte.
    valores = matriz.astype(np.float32) * float(corte.get("RescaleSlope", 1)) + float(corte.get("RescaleIntercept", 0))  # Aplica la calibración disponible.
    utilizables = np.ones(matriz.shape, dtype=bool)  # Inicializa la máscara de validez.
    if "PixelPaddingValue" in corte:  # Contempla padding declarado en el torso.
        extremos = sorted([float(corte.PixelPaddingValue), float(corte.get("PixelPaddingRangeLimit", corte.PixelPaddingValue))])  # Obtiene sus límites.
        utilizables &= ~((matriz >= extremos[0]) & (matriz <= extremos[1]))  # Elimina el relleno del histograma.
    valores = valores[utilizables]  # Selecciona valores con interpretación física.
    hist_torax += np.histogram(valores, bins=bordes_hu)[0]  # Suma las frecuencias de cada corte.
    fuera_torax += np.count_nonzero((valores < bordes_hu[0]) | (valores > bordes_hu[-1]))  # Cuenta los valores fuera de rango.
fig, ax = plt.subplots(figsize=(10, 4))  # Prepara una comparación normalizada.
ax.stairs(hist_ge / hist_ge.sum(), bordes_hu, label="Cráneo GE")  # Representa proporciones del cráneo.
ax.stairs(hist_torax / hist_torax.sum(), bordes_hu, label="Tórax")  # Representa proporciones del tórax.
ax.axvspan(-900, -500, color="skyblue", alpha=0.25, label="Intervalo orientativo de pulmón")  # Destaca el rango de interés.
ax.set(xlabel="HU", ylabel="Fracción de píxeles en cada intervalo", title="Distribuciones de HU")  # Nombra las magnitudes.
ax.legend()  # Identifica las series y el intervalo.
plt.show()  # Muestra la comparación.
print("Tórax: valores válidos fuera del rango mostrado:", fuera_torax)  # Documenta el recorte del eje HU.
''')
code('''### 3.4 · Definir una ventana de visualización
El nivel fija el centro y el ancho fija el intervalo visible. Saturamos con `np.clip` y normalizamos a [0,1]; no modificamos los HU originales. Esta es una ventana lineal didáctica, no una implementación completa de VOI LUT ni de todas las convenciones DICOM de presentación. Se espera que el centro se represente como gris medio.''', '''
def ventana(hu, nivel, ancho, normalizar=True):  # Permite visualizar en escala normalizada o conservar HU para exportar.
    inferior = nivel - ancho / 2  # Calcula el extremo negro del intervalo.
    superior = nivel + ancho / 2  # Calcula el extremo blanco del intervalo.
    recortada = np.clip(hu, inferior, superior)  # Limita los valores al intervalo visible sin cambiar el arreglo original.
    if normalizar:  # Mantiene la presentación normalizada utilizada durante el taller.
        return (recortada - inferior) / ancho  # Convierte la ventana al intervalo de visualización [0,1].
    return recortada  # Conserva unidades HU para usar vmin y vmax físicos al exportar.
print("Negro, gris medio y blanco:", ventana(np.array([0, 40, 80]), 40, 80))  # Comprueba una ventana de cerebro.
''')
code('''### 3.5 · Tres ventanas del mismo cráneo
Aplicamos cerebro 40/80, tejido blando 40/400 y hueso 400/1800, expresados como nivel/ancho en HU. Se espera reconocer cómo una misma matriz permite destacar distintos tejidos; las imágenes no son adquisiciones diferentes.''', '''
ventanas_craneo = [("Cerebro · 40/80", 40, 80), ("Tejido blando · 40/400", 40, 400), ("Hueso · 400/1800", 400, 1800)]  # Define las tres presentaciones.
fig_ventanas, ejes = plt.subplots(1, 3, figsize=(15, 5))  # Sitúa las ventanas lado a lado.
for ax, (nombre, nivel, ancho) in zip(ejes, ventanas_craneo):  # Recorre las tres ventanas.
    ax.imshow(ventana(hu_craneo, nivel, ancho), cmap="gray", vmin=0, vmax=1)  # Visualiza siempre 18.dcm.
    ax.set_title(nombre)  # Identifica nivel y ancho de cada presentación.
    ax.axis("off")  # Oculta los ejes de matriz.
fig_ventanas.tight_layout()  # Evita superposiciones entre paneles.
plt.show()  # Muestra la comparación.
''')
code('''### El cerebro humano también está en la CT GE
El cráneo es el hueso que rodea al encéfalo; no son la misma estructura. En `18.dcm`, la ventana cerebral permite observar tejidos intracraneales, mientras que la ventana ósea destaca la pared del cráneo. Ampliamos la presentación cerebral del mismo corte para reconocer esa diferencia. **La ventana no separa ni segmenta el cerebro**: solamente cambia la escala de grises. El fantoma Philips no contiene un cerebro humano. Se espera ver el contenido intracraneal con mayor contraste y el hueso saturado.''', '''
fig_cerebro, ejes = plt.subplots(1, 2, figsize=(13, 6))  # Compara contenido intracraneal y envoltura ósea en el mismo corte humano.
for ax, nivel, ancho, titulo in [(ejes[0], 40, 80, "Cerebro humano · ventana cerebral"), (ejes[1], 400, 1800, "Cráneo · ventana ósea")]:  # Define dos presentaciones de 18.dcm.
    ax.imshow(ventana(hu_craneo, nivel, ancho), cmap="gray", vmin=0, vmax=1)  # Visualiza los HU originales con la ventana correspondiente.
    ax.set_title(titulo)  # Distingue explícitamente cerebro y cráneo.
    ax.axis("off")  # Mantiene la atención sobre la anatomía visible.
plt.show()  # Presenta las dos imágenes a mayor tamaño.
''')
code('''### Recorrer los cortes del cerebro humano
Un único corte no muestra todo el encéfalo. Leemos los 28 archivos GE, ordenamos por posición z y añadimos un slider. Cada imagen se calibra de forma independiente y se muestra en ventana cerebral; `18.dcm` sigue siendo el archivo de referencia para los ejemplos anteriores. Se espera recorrer desde cortes inferiores hasta superiores. No construiremos una rejilla 3D regular de esta serie, porque tiene inclinación del gantry y separaciones variables. Para obtener una superficie 3D fiable del cerebro harían falta una adquisición adecuada y una segmentación específica; el umbral de hueso no sirve para ello.''', '''
cortes_ge_cerebro = [pydicom.dcmread(ruta) for ruta in archivos_ge]  # Lee los cortes humanos sin cambiar el archivo de referencia ds.
cortes_ge_cerebro.sort(key=lambda c: float(c.ImagePositionPatient[2]))  # Ordena la navegación por posición física.
indice_referencia = next(i for i, c in enumerate(cortes_ge_cerebro) if Path(c.filename).name == "18.dcm")  # Inicia la exploración en el corte de referencia.
def explorar_cerebro(indice):  # Define la visualización de un solo corte humano.
    corte_cerebro = cortes_ge_cerebro[indice]  # Selecciona el Dataset señalado por el slider.
    hu_cerebro = corte_cerebro.pixel_array.astype(np.float32) * float(corte_cerebro.RescaleSlope) + float(corte_cerebro.RescaleIntercept)  # Aplica la calibración propia de este corte.
    fig, ax = plt.subplots(figsize=(7, 7))  # Amplía la imagen para inspeccionar tejido intracraneal.
    ax.imshow(ventana(hu_cerebro, 40, 80), cmap="gray", vmin=0, vmax=1)  # Usa ventana cerebral constante al recorrer la serie.
    ax.set_title(f"Cerebro humano · {Path(corte_cerebro.filename).name} · corte {indice + 1}/{len(cortes_ge_cerebro)}")  # Identifica el archivo visualizado.
    ax.axis("off")  # Oculta índices de matriz.
    plt.show()  # Muestra el corte seleccionado.
    plt.close(fig)  # Libera la figura después de visualizarla.
control_cerebro = widgets.interactive(explorar_cerebro, indice=widgets.IntSlider(value=indice_referencia, min=0, max=len(cortes_ge_cerebro) - 1, description="Corte", continuous_update=False))  # Crea el control de navegación por cortes.
display(control_cerebro)  # Presenta el slider y la vista cerebral.
''')
code('''### 3.6 · Pulmón y mediastino en el corte central del tórax
Elegimos el corte central de la serie ordenada y usamos su propia calibración. Comparamos pulmón −600/1500 y mediastino 40/400. Se espera un mayor detalle del parénquima pulmonar en la primera y de tejidos blandos centrales en la segunda.''', '''
central_torax = cortes_torax[len(cortes_torax) // 2]  # Selecciona un corte intermedio por posición.
hu_torax_central = central_torax.pixel_array.astype(np.float32) * float(central_torax.get("RescaleSlope", 1)) + float(central_torax.get("RescaleIntercept", 0))  # Calibra ese corte a HU.
fig_torax, ejes = plt.subplots(1, 2, figsize=(12, 6))  # Crea dos paneles comparables.
for ax, (nombre, nivel, ancho) in zip(ejes, [("Pulmón · −600/1500", -600, 1500), ("Mediastino · 40/400", 40, 400)]):  # Recorre las dos ventanas.
    ax.imshow(ventana(hu_torax_central, nivel, ancho), cmap="gray", vmin=0, vmax=1)  # Muestra el mismo corte en cada panel.
    ax.set_title(nombre)  # Indica los parámetros de presentación.
    ax.axis("off")  # Oculta los índices.
plt.show()  # Presenta el contraste entre ventanas.
''')
md('''
### Ejercicio 2 · Reconocer las ventanas
Observe las imágenes A, B y C de la siguiente celda, sin títulos de tejido. Asigne «hueso», «cerebro» y «tejido blando» y justifique su decisión por el contraste y la saturación. ¿Por qué no conviene medir HU sobre la imagen ya normalizada?
''')
code('''### Imágenes del ejercicio 2
Reordenamos las tres ventanas del mismo `18.dcm` y usamos únicamente letras. Se espera identificar cada presentación sin cambiar los HU originales; contraste y saturación proporcionan pistas.''', '''
fig, ejes = plt.subplots(1, 3, figsize=(15, 5))  # Prepara tres paneles sin títulos de tejido.
for ax, (letra, nivel, ancho) in zip(ejes, [("A", 400, 1800), ("B", 40, 80), ("C", 40, 400)]):  # Fija exactamente el orden solicitado.
    ax.imshow(ventana(hu_craneo, nivel, ancho), cmap="gray", vmin=0, vmax=1)  # Aplica la ventana del panel.
    ax.text(0.05, 0.95, letra, transform=ax.transAxes, color="yellow", fontsize=20, va="top")  # Etiqueta sin nombrar el tejido.
    ax.axis("off")  # Evita títulos o ejes que den pistas adicionales.
plt.show()  # Presenta las tres imágenes del ejercicio.
''')
md('''
### Solución · Ejercicio 2
**A = hueso (400/1800), B = cerebro (40/80), C = tejido blando (40/400).**

A conserva diferencias entre estructuras de alta atenuación; B amplifica diferencias pequeñas de tejido cerebral y satura el hueso; C abarca un rango mayor de tejidos blandos. Después de `clip`, distintos HU pueden convertirse en el mismo negro o blanco: la transformación no es invertible en las zonas saturadas. Las mediciones se hacen sobre `hu_craneo`, nunca sobre la imagen ventaneada.
''')
code('''### Bonus · Ventaneo en vivo
Movemos nivel y ancho con sliders y elegimos cráneo o tórax. El ancho mínimo es positivo para evitar división por cero. Se espera una actualización al soltar el control; la calibración permanece intacta.''', '''
try:  # Activa el gestor de widgets cuando estamos en Colab.
    from google.colab import output  # Importa la integración de widgets de Colab.
    output.enable_custom_widget_manager()  # Habilita los controles interactivos.
except ImportError:  # Permite abrir el notebook fuera de Colab.
    pass  # Usa el gestor estándar de Jupyter si está disponible.
def explorar_ventana(imagen, nivel, ancho):  # Define solamente la operación de presentación.
    hu = hu_craneo if imagen == "Cráneo" else hu_torax_central  # Escoge el arreglo de HU correspondiente.
    fig, ax = plt.subplots(figsize=(6, 6))  # Crea una figura para la actualización actual.
    ax.imshow(ventana(hu, nivel, ancho), cmap="gray", vmin=0, vmax=1)  # Aplica los parámetros del usuario.
    ax.set_title(f"{imagen} · nivel {nivel} · ancho {ancho}")  # Informa los valores activos.
    ax.axis("off")  # Oculta los índices.
    plt.show()  # Muestra la imagen actualizada.
    plt.close(fig)  # Libera la figura después de presentarla.
control = widgets.interactive(explorar_ventana, imagen=widgets.Dropdown(options=["Cráneo", "Tórax"]), nivel=widgets.IntSlider(value=40, min=-1000, max=1000, step=10, continuous_update=False), ancho=widgets.IntSlider(value=400, min=10, max=2500, step=10, continuous_update=False))  # Vincula selector y sliders a la función.
display(control)  # Presenta los controles en la salida de la celda.
''')
md('''
<a id="parte4"></a>
## Parte 4 · Reconstrucción y visualización 3D
Un volumen organiza cortes como `volumen[z, y, x]`. El espaciado asociado tiene el mismo orden **(dz, dy, dx)**. No se debe ordenar por nombre de archivo: los nombres carecen de significado espacial y el orden lexicográfico puede situar `10` antes que `2`.

Para estas series axiales, ordenaremos por `ImagePositionPatient[2]` y estimaremos `dz` con las diferencias entre posiciones. En un caso general, la ordenación se hace proyectando la posición sobre la normal calculada a partir de `ImageOrientationPatient`, y puede requerir remuestreo. Una mediana de separaciones no corrige cortes irregulares ni gantry inclinado.

**GE se excluye de la reconstrucción 3D:** tiene gantry inclinado (+18,5° en la referencia) y grosores variables de 4 a 7 mm, además de posiciones no uniformes. Apilarlo directamente como una rejilla regular distorsionaría la geometría. Usaremos el fantoma Philips de cortes nominales de 1 mm y verificaremos sus posiciones y orientación, así como las del tórax.
''')
code('''### 4.1 · Cargar una serie en HU y comprobar la rejilla
La función lee todos los archivos recursivamente, incluidos los que carecen de extensión, filtra posición y píxeles, verifica que solo haya una serie y ordena por z. Devuelve volumen y espaciado medido. Se espera una rejilla regular y axial para Philips y tórax; el código informa la orientación y rechaza datos con geometría incompatible, en lugar de ocultar distorsiones.''', '''
def cargar_serie(carpeta):  # Agrupa la lectura y las comprobaciones geométricas necesarias.
    cortes = []  # Acumula las imágenes válidas.
    for ruta in Path(carpeta).rglob("*"):  # Busca archivos también en subcarpetas.
        if not ruta.is_file():  # Omite directorios.
            continue  # Pasa al siguiente elemento.
        try:  # Permite ignorar archivos auxiliares.
            corte = pydicom.dcmread(ruta, force=True)  # Lee DICOM incluso sin preámbulo.
            if "ImagePositionPatient" in corte and corte.pixel_array.ndim == 2:  # Exige posición y una matriz monocroma 2D.
                cortes.append(corte)  # Conserva la instancia utilizable.
        except Exception:  # Descarta archivos que no se pueden leer como cortes.
            continue  # Continúa con el resto de la carpeta.
    assert len(cortes) > 1, "La carpeta no contiene una serie de cortes válida."  # Evita construir un volumen vacío.
    assert len({str(c.SeriesInstanceUID) for c in cortes}) == 1, "La carpeta mezcla series; seleccione una sola."  # Evita combinar adquisiciones distintas.
    cortes.sort(key=lambda c: float(c.ImagePositionPatient[2]))  # Ordena físicamente de inferior a superior.
    posiciones = np.array([c.ImagePositionPatient for c in cortes], dtype=float)  # Reúne coordenadas de los centros de corte.
    diferencias_z = np.diff(posiciones[:, 2])  # Calcula distancias sucesivas sobre z.
    dz = float(np.median(diferencias_z))  # Estima separación entre centros, no grosor de corte.
    dy, dx = map(float, cortes[0].PixelSpacing)  # Recupera espaciados de filas y columnas.
    orientacion = np.array(cortes[0].ImageOrientationPatient, dtype=float)  # Lee cosenos directores de los ejes de imagen.
    print("Cortes:", len(cortes), "dz mínimo/mediano/máximo:", diferencias_z.min(), dz, diferencias_z.max())  # Expone regularidad de las posiciones.
    print("Orientación:", orientacion, "Espaciado (dz,dy,dx):", (dz, dy, dx))  # Documenta la geometría que se utilizará.
    assert dz > 0 and np.allclose(diferencias_z, dz, atol=0.05, rtol=0.01), "Separación irregular: se necesita remuestreo."  # Rechaza huecos o posiciones repetidas.
    assert np.allclose(orientacion, [1, 0, 0, 0, 1, 0], atol=0.01), "Serie oblicua: requiere reorientación antes de estas MPR."  # Limita las vistas simples a ejes axiales convencionales.
    assert np.allclose(posiciones[:, :2], posiciones[0, :2], atol=0.1), "Desplazamiento entre cortes: posible inclinación del gantry."  # Detecta cizallamiento de la rejilla.
    assert all(np.allclose(c.ImageOrientationPatient, orientacion, atol=0.01) for c in cortes), "La orientación cambia entre cortes."  # Exige ejes consistentes.
    assert all(np.allclose(c.PixelSpacing, [dy, dx]) and (int(c.Rows), int(c.Columns)) == (int(cortes[0].Rows), int(cortes[0].Columns)) for c in cortes), "Tamaño o espaciado variable."  # Exige una rejilla uniforme.
    volumen = np.stack([c.pixel_array.astype(np.float32) * float(c.get("RescaleSlope", 1)) + float(c.get("RescaleIntercept", 0)) for c in cortes])  # Apila los cortes calibrados individualmente a HU.
    return volumen, (dz, dy, dx)  # Devuelve matriz y espaciado en el mismo orden de ejes.
vol_philips, esp_philips = cargar_serie(CARPETA_PHILIPS)  # Construye el volumen del fantoma de cráneo.
vol_torax, esp_torax = cargar_serie(CARPETA_TORAX)  # Construye el volumen de torso humano.
print("Formas (z,y,x):", vol_philips.shape, vol_torax.shape)  # Confirma la organización de ambos volúmenes.
''')
code('''### 4.2 · MPR del fantoma Philips
Una reconstrucción multiplanar (MPR) extrae planos ortogonales del volumen. Corregimos la relación física de los píxeles con `dz/dx` en coronal y `dz/dy` en sagital; en axial usamos `dy/dx`. Invertimos z con `[::-1]` y `origin='upper'` para que el extremo superior de la cabeza quede arriba. Son vistas de la rejilla axial comprobada, sin registro ni interpolación a una rejilla isotrópica. Se espera observar el fantoma en tres planos sin estirar su anatomía.''', '''
def mostrar_mpr(volumen, espaciado, nivel, ancho, titulo):  # Reutiliza las mismas reglas de visualización en ambas series.
    dz, dy, dx = espaciado  # Desempaqueta distancias físicas en orden z,y,x.
    z, y, x = np.array(volumen.shape) // 2  # Selecciona los índices centrales del volumen.
    planos = [volumen[z, :, :], volumen[::-1, y, :], volumen[::-1, :, x]]  # Extrae axial y planos verticales con z invertido.
    aspectos = [dy / dx, dz / dx, dz / dy]  # Corrige la proporción entre dimensión vertical y horizontal.
    fig, ejes = plt.subplots(1, 3, figsize=(15, 6))  # Prepara los tres paneles de la MPR.
    for ax, plano, aspecto, nombre in zip(ejes, planos, aspectos, ["Axial", "Coronal", "Sagital"]):  # Recorre cortes y geometría correspondiente.
        ax.imshow(ventana(plano, nivel, ancho), cmap="gray", vmin=0, vmax=1, aspect=aspecto, origin="upper")  # Conserva relaciones de aspecto físicas.
        ax.set_title(f"{titulo} · {nombre}")  # Identifica la serie y el plano.
        ax.axis("off")  # Oculta índices que podrían confundirse con milímetros.
    fig.tight_layout()  # Ajusta el espacio entre vistas.
    return fig  # Conserva la figura para exportación posterior.
fig_mpr_philips = mostrar_mpr(vol_philips, esp_philips, 400, 1800, "Fantoma Philips")  # Visualiza el fantoma en ventana de hueso.
plt.show()  # Presenta la MPR del cráneo de maniquí.
''')
code('''### 4.3 · MPR del tórax con ventana de pulmón
Aplicamos el mismo procedimiento, ahora con el espaciado del torso y ventana −600/1500. Se espera comparar continuidad y extensión del pulmón entre planos. El paso entre cortes puede producir un aspecto escalonado: corregir el aspecto no crea información nueva.''', '''
fig_mpr_torax = mostrar_mpr(vol_torax, esp_torax, -600, 1500, "Tórax · pulmón")  # Genera las tres vistas con escala física correcta.
plt.show()  # Presenta la reconstrucción multiplanar de tórax.
''')
md('''
### De vóxeles a superficies
**Marching cubes**, presentado por **William E. Lorensen y Harvey E. Cline en SIGGRAPH 1987**, aproxima una isosuperficie mediante triángulos. [Artículo original, DOI 10.1145/37401.37422](https://doi.org/10.1145/37401.37422).

El umbral decide qué material entra en la máscara; el muestreo y el suavizado modifican el detalle geométrico. Ninguna de estas superficies equivale a una segmentación anatómica validada. Para reducir cómputo en CPU submuestreamos solo y/x y actualizamos sus espaciados. Se conserva la componente conectada mayor para retirar estructuras separadas, como la camilla; si camilla y cráneo estuvieran conectados, esa regla sería insuficiente y habría que revisar la máscara.
''')
code('''### 4.4 · Extraer la superficie ósea del fantoma
Reducimos el volumen con `[:, ::2, ::2]`, umbralizamos a 300 HU y seleccionamos la componente mayor con `measure.label`. Suavizamos levemente la máscara y extraemos su isosuperficie de 0,5. Se espera una malla del fantoma, con vértices en mm y no en índices. Mostramos además una proyección de la máscara para comprobar que no incluya la camilla.''', '''
sub_philips = vol_philips[:, ::2, ::2]  # Reduce filas y columnas sin reducir el eje z.
esp_malla = (esp_philips[0], esp_philips[1] * 2, esp_philips[2] * 2)  # Compensa el submuestreo en las distancias físicas.
etiquetas = measure.label(sub_philips > 300, connectivity=1)  # Etiqueta componentes de material de alta atenuación.
tamanos = np.bincount(etiquetas.ravel())  # Cuenta los vóxeles de cada componente.
tamanos[0] = 0  # Excluye el fondo de la selección.
assert tamanos.max() > 0, "No hay componentes sobre 300 HU."  # Comprueba que existe una superficie extraíble.
mascara_craneo = etiquetas == tamanos.argmax()  # Conserva solamente la mayor componente conectada.
suave = ndimage.gaussian_filter(mascara_craneo.astype(np.float32), sigma=0.7)  # Suaviza levemente la máscara binaria.
vertices, caras, normales, valores = measure.marching_cubes(suave, level=0.5, spacing=esp_malla)  # Extrae vértices en coordenadas locales z,y,x medidas en mm.
print("Vértices:", len(vertices), "Triángulos:", len(caras))  # Dimensiona el resultado geométrico.
fig, ax = plt.subplots(figsize=(6, 5))  # Prepara un control de la componente seleccionada.
ax.imshow(mascara_craneo.max(axis=0), cmap="gray")  # Muestra la proyección axial de la máscara.
ax.set_title("Control: componente mayor del fantoma")  # Invita a revisar estructuras retenidas.
ax.axis("off")  # Oculta los índices de la máscara.
plt.show()  # Presenta la comprobación antes del render.
''')
code('''### Mostrar el fantoma con Plotly Mesh3d
Reordenamos vértices de (z,y,x) a los ejes (x,y,z) de la gráfica y usamos proporción física `aspectmode='data'`. Se espera un cráneo color `ivory` que pueda rotar y ampliar con el ratón. Las coordenadas son locales al volumen, no coordenadas absolutas del paciente.''', '''
fig_3d = go.Figure(data=[go.Mesh3d(x=vertices[:, 2], y=vertices[:, 1], z=vertices[:, 0], i=caras[:, 0], j=caras[:, 1], k=caras[:, 2], color="ivory", opacity=1, flatshading=False)])  # Construye la superficie triangular interactiva.
fig_3d.update_layout(title="Fantoma Philips · superficie > 300 HU", scene=dict(aspectmode="data", xaxis_title="x local (mm)", yaxis_title="y local (mm)", zaxis_title="z local (mm)"), paper_bgcolor="black", font_color="white", margin=dict(l=0, r=0, b=0, t=45))  # Mantiene proporciones y unidades físicas.
fig_3d.show(renderer="colab")  # Presenta el render interactivo en Google Colab.
''')
code('''### Bonus · Pulmones en 3D: de la imagen a una máscara
Una **máscara** es una matriz que marca los vóxeles seleccionados. Aquí buscamos regiones de baja atenuación dentro del cuerpo para aproximar la forma de los pulmones. Antes del render **«Pulmones · segmentación por umbral»** veremos qué se seleccionó sobre la CT: el color marca la región que se convertirá en superficie.

Creamos un contorno corporal por corte, eliminamos el aire exterior conectado al borde y conservamos regiones grandes de baja atenuación. Rellenamos huecos pequeños en cada sección pulmonar y seleccionamos hasta dos componentes 3D relevantes. Se espera distinguir dos volúmenes pulmonares reconocibles; la máscara no representa todo el tejido pulmonar y puede excluir zonas densas o incluir vía aérea y gas. Este ejemplo no es una segmentación validada ni un cálculo de volumen clínico.''', '''
sub_torax = vol_torax[:, ::2, ::2]  # Reduce el coste de la segmentación y la malla.
mascara_pulmon = np.zeros(sub_torax.shape, dtype=bool)  # Inicializa una máscara tridimensional vacía.
for z, plano in enumerate(sub_torax):  # Procesa el torso corte a corte.
    etiquetas_cuerpo = measure.label(plano > -400, connectivity=1)  # Separa tejidos corporales y objetos densos.
    tamanos_cuerpo = np.bincount(etiquetas_cuerpo.ravel())  # Calcula el área de cada componente.
    tamanos_cuerpo[0] = 0  # Excluye el fondo de la elección corporal.
    if tamanos_cuerpo.max() == 0:  # Contempla cortes sin cuerpo detectable.
        continue  # Deja vacía la máscara de ese corte.
    cuerpo = ndimage.binary_fill_holes(etiquetas_cuerpo == tamanos_cuerpo.argmax())  # Recupera el interior del contorno corporal, incluidos pulmones.
    etiquetas_aire = measure.label(plano < -400, connectivity=1)  # Identifica las regiones de baja atenuación.
    borde = np.unique(np.concatenate([etiquetas_aire[0, :], etiquetas_aire[-1, :], etiquetas_aire[:, 0], etiquetas_aire[:, -1]]))  # Identifica aire conectado al exterior de la imagen.
    aire_interno = (etiquetas_aire > 0) & ~np.isin(etiquetas_aire, borde)  # Retira las componentes conectadas al borde.
    candidatos = measure.label(aire_interno & cuerpo, connectivity=1)  # Separa las regiones internas de baja atenuación.
    areas = np.bincount(candidatos.ravel())  # Mide las regiones candidatas en este corte.
    areas[0] = 0  # Excluye el fondo de la selección.
    regiones = np.flatnonzero(areas > 200)  # Descarta pequeñas bolsas de aire y ruido.
    elegidas = regiones[np.argsort(areas[regiones])[-2:]]  # Conserva como máximo las dos regiones mayores del corte.
    mascara_pulmon[z] = ndimage.binary_fill_holes(np.isin(candidatos, elegidas)) & cuerpo  # Rellena vasos internos pequeños y restringe al cuerpo.
etiquetas_pulmon = measure.label(mascara_pulmon, connectivity=1)  # Conecta candidatos pulmonares entre cortes.
tamanos_pulmon = np.bincount(etiquetas_pulmon.ravel())  # Mide los candidatos tridimensionales.
tamanos_pulmon[0] = 0  # Excluye el fondo del ordenamiento.
componentes = np.flatnonzero(tamanos_pulmon > max(1000, tamanos_pulmon.max() * 0.10))  # Descarta regiones pequeñas respecto al componente pulmonar dominante.
mayores = componentes[np.argsort(tamanos_pulmon[componentes])[-2:]]  # Selecciona como máximo dos regiones grandes.
mascara_pulmon = np.isin(etiquetas_pulmon, mayores)  # Forma la máscara final aproximada.
indices_control = [len(sub_torax) // 3, len(sub_torax) // 2, 2 * len(sub_torax) // 3]  # Selecciona tres niveles para revisar qué se segmentó.
fig_control_pulmon, ejes = plt.subplots(1, 3, figsize=(15, 5))  # Crea una explicación visual previa al render.
for ax, indice in zip(ejes, indices_control):  # Recorre tres cortes representativos.
    ax.imshow(ventana(sub_torax[indice], -600, 1500), cmap="gray", vmin=0, vmax=1)  # Muestra la CT con ventana de pulmón.
    ax.imshow(np.ma.masked_where(~mascara_pulmon[indice], mascara_pulmon[indice]), cmap="autumn", vmin=0, vmax=1, alpha=0.35)  # Resalta únicamente los píxeles seleccionados por la máscara.
    ax.set_title(f"Pulmones seleccionados · corte {indice + 1}")  # Explica la superposición coloreada.
    ax.axis("off")  # Oculta índices que no aportan a la interpretación.
plt.show()  # Permite revisar la selección antes de observarla en 3D.
if mascara_pulmon.any():  # Evita extraer una isosuperficie inexistente.
    suave_pulmon = ndimage.gaussian_filter(mascara_pulmon.astype(np.float32), sigma=0.7)  # Reduce discretización de los bordes.
    vp, cp, _, _ = measure.marching_cubes(suave_pulmon, level=0.5, spacing=(esp_torax[0], esp_torax[1] * 2, esp_torax[2] * 2))  # Extrae malla con espaciado actualizado.
    fig_pulmon = go.Figure(data=[go.Mesh3d(x=vp[:, 2], y=vp[:, 1], z=vp[:, 0], i=cp[:, 0], j=cp[:, 1], k=cp[:, 2], color="lightskyblue", opacity=0.9)])  # Construye la superficie pulmonar aproximada.
    uid_segmentacion_pulmon = str(cortes_torax[0].SeriesInstanceUID)  # Registra la procedencia para no exportar la malla como si fuera de otro estudio.
    fig_pulmon.update_layout(title="Pulmones · segmentación por umbral", scene=dict(aspectmode="data", xaxis_title="x (mm)", yaxis_title="y (mm)", zaxis_title="z (mm)"), paper_bgcolor="black", font_color="white")  # Nombra el órgano y el método, conservando la escala física.
    fig_pulmon.show(renderer="colab")  # Permite inspeccionar la segmentación desde distintos ángulos.
else:  # Contempla el fracaso de esta estrategia de umbral simple.
    print("No se obtuvo una máscara pulmonar; revise el umbral y el contorno corporal.")  # Explica la ausencia de render sin detener el notebook.
''')
md('''
<a id="conclusiones"></a>
## Conclusiones · Un pequeño pipeline de investigación
Un flujo de investigación relaciona procedencia de datos, protección de información, calibración, geometría y resultados verificables. Cerraremos con dos salidas: una copia DICOM con eliminación ilustrativa de identificadores y un NIfTI del fantoma.

**La eliminación de unos pocos tags no garantiza anonimización.** Aquí se muestra una operación didáctica sobre datos públicos ya desidentificados. Permanecen otros atributos (por ejemplo, PatientID), UID, fechas y posibles identificadores en secuencias o píxeles. Para uso real se requiere un procedimiento completo conforme al [perfil de confidencialidad DICOM, PS3.15](https://dicom.nema.org/medical/dicom/current/output/chtml/part15/chapter_E.html), evaluación del riesgo y verificación. La copia no debe redistribuirse como si esta celda certificara su anonimización.
''')
code('''### Guardar una copia DICOM con supresión ilustrativa de identificadores
Usamos una copia profunda de `18.dcm`, retiramos tags privados y borramos `PatientName` y `PatientBirthDate`. Conservamos el original y verificamos la copia releyéndola. Se espera ausencia de esos tags, ningún tag privado y píxeles idénticos; esto comprueba únicamente las operaciones realizadas.''', '''
SALIDAS = BASE / "salidas_sipaim"  # Define una carpeta de resultados separada de los datos fuente.
SALIDAS.mkdir(exist_ok=True)  # Crea el destino sin borrar resultados anteriores.
ds_copia = copy.deepcopy(ds)  # Protege el Dataset original y sus secuencias.
ds_copia.remove_private_tags()  # Elimina elementos privados, también en secuencias.
for nombre in ["PatientName", "PatientBirthDate"]:  # Recorre los dos atributos solicitados.
    if nombre in ds_copia:  # Tolera la ausencia de cualquiera de ellos.
        del ds_copia[nombre]  # Borra el atributo de la copia.
ruta_copia = SALIDAS / "18_sin_identificadores_directos_demo.dcm"  # Nombra explícitamente la copia didáctica.
ds_copia.save_as(ruta_copia, enforce_file_format=True)  # Escribe un archivo DICOM con formato completo.
verificacion = pydicom.dcmread(ruta_copia)  # Relee lo escrito para validar el resultado.
assert "PatientName" not in verificacion and "PatientBirthDate" not in verificacion, "No se eliminaron los tags solicitados."  # Comprueba la supresión solicitada.
assert not any(e.tag.is_private for e in verificacion.iterall()), "Quedan tags privados."  # Comprueba la retirada recursiva de privados.
assert np.array_equal(verificacion.pixel_array, crudo), "La copia cambió los píxeles."  # Verifica la integridad de la imagen.
print("Copia verificada:", ruta_copia, "— demostración parcial, no anonimización certificada.")  # Delimita el alcance de la operación.
''')
code('''### Convertir el fantoma Philips a NIfTI con SimpleITK
GDCM identifica las series y ordena sus archivos por geometría, incluso sin extensión. Seleccionamos el UID del fantoma ya analizado, leemos la serie y guardamos `.nii.gz`. Al releer, comparamos tamaño, espaciado y geometría. SimpleITK usa **(x,y,z)** para tamaño/espaciado; sus arreglos NumPy usan **(z,y,x)**. Se espera que la forma coincida con `vol_philips` y que el espaciado concuerde con el medido a partir de posiciones.''', '''
uid_philips = str(series_iniciales["Philips"][0].SeriesInstanceUID)  # Identifica exactamente la serie de fantoma seleccionada.
nombres_sitk = sitk.ImageSeriesReader.GetGDCMSeriesFileNames(str(CARPETA_PHILIPS), uid_philips)  # Obtiene los archivos en orden espacial con GDCM.
assert len(nombres_sitk) == vol_philips.shape[0], "GDCM y pydicom no seleccionaron los mismos cortes."  # Controla la selección de serie.
lector = sitk.ImageSeriesReader()  # Crea el lector de series DICOM.
lector.SetFileNames(nombres_sitk)  # Asigna los archivos ordenados geométricamente.
imagen_sitk = lector.Execute()  # Lee la serie y aplica la calibración DICOM.
ruta_nifti = SALIDAS / "fantoma_philips.nii.gz"  # Define la salida comprimida de investigación.
sitk.WriteImage(imagen_sitk, str(ruta_nifti))  # Escribe el volumen y su geometría en NIfTI.
imagen_releida = sitk.ReadImage(str(ruta_nifti))  # Verifica el archivo realmente guardado.
forma_releida = sitk.GetArrayFromImage(imagen_releida).shape  # Consulta la forma en orden NumPy z,y,x.
print("Forma NumPy (z,y,x):", forma_releida, "Espaciado SITK (x,y,z):", imagen_releida.GetSpacing())  # Muestra ambas convenciones.
assert forma_releida == vol_philips.shape, "La forma no coincide."  # Verifica que no se perdieron cortes.
assert np.allclose(imagen_releida.GetSpacing()[::-1], esp_philips, atol=0.05), "El espaciado no coincide."  # Compara espaciados en el mismo orden.
assert np.allclose(imagen_releida.GetOrigin(), imagen_sitk.GetOrigin(), atol=1e-3) and np.allclose(imagen_releida.GetDirection(), imagen_sitk.GetDirection(), atol=1e-5), "Cambió la geometría al guardar."  # Controla origen y orientación en la ida y vuelta.
assert np.allclose(sitk.GetArrayFromImage(imagen_releida), sitk.GetArrayFromImage(imagen_sitk), atol=1e-3), "Cambió la intensidad al guardar."  # Comprueba que la conversión conserva intensidades.
print("NIfTI verificado:", ruta_nifti)  # Confirma el resultado del pequeño pipeline.
''')
md('''
### Cuatro ideas para llevarse
1. **DICOM integra imagen y metadatos:** el contexto y la geometría son parte del dato.
2. **El CT se calibra en HU:** la conversión usa los parámetros de cada imagen.
3. **El ventaneo define qué tejidos se ven:** mejora la presentación, pero no reemplaza las intensidades físicas.
4. **El volumen permite MPR y render 3D:** comprobar orden, orientación y espaciado es imprescindible.

Para discutir: ¿qué se perdería al exportar únicamente un PNG? ¿Qué comprobaciones añadiría antes de procesar una colección de cientos de estudios? ¿Cómo validaría una segmentación obtenida por umbral?

<a id="recursos"></a>
## Recursos, créditos y licencias
### Continuar aprendiendo
- [pydicom: documentación oficial](https://pydicom.github.io/pydicom/stable/): elementos, píxeles y ejemplos de lectura.
- [SimpleITK: lectura de series DICOM](https://simpleitk.readthedocs.io/en/master/link_DicomSeriesReader_docs.html): geometría y conversión de volúmenes.
- [MONAI](https://monai.io/): herramientas de aprendizaje profundo para investigación en imagen médica.
- [3D Slicer](https://www.slicer.org/): inspección, segmentación y visualización de volúmenes.
- [NCI Imaging Data Commons](https://imaging.datacommons.cancer.gov/) y [API de idc-index](https://idc-index.readthedocs.io/en/latest/api/idc_index.html): datos públicos, consulta y descarga reproducible.
- [AWS HealthImaging](https://aws.amazon.com/healthimaging/): servicio administrado de almacenamiento y acceso a imágenes médicas.
- [Estándar DICOM](https://www.dicomstandard.org/current): referencia normativa para representación, intercambio y confidencialidad.

### Datos y atribución
- **[dcm_qa_ct](https://github.com/neurolabusc/dcm_qa_ct)**: Chris Rorden (C. Rorden), licencia **BSD de 2 cláusulas (BSD-2-Clause)**. CT humano GE HiSpeed Dual, cortesía de **Aliza Medical Imaging**. Fantoma de cráneo Philips Ingenuity, cortesía de **Paul Morgan (P. Morgan), Nottingham Medical School**. Conserve el aviso de copyright y el texto de [la licencia del repositorio](https://github.com/neurolabusc/dcm_qa_ct/blob/master/LICENSE) al redistribuir los datos. La selección Philips de este taller es `In/Philips/S21570/S2020`.
- **[LIDC-IDRI](https://www.cancerimagingarchive.net/collection/lidc-idri/)**: Armato III, S. G., McLennan, G., Bidaut, L. y colaboradores (2015). *Data From LIDC-IDRI*. The Cancer Imaging Archive. [DOI 10.7937/K9/TCIA.2015.LO9QL9SX](https://doi.org/10.7937/K9/TCIA.2015.LO9QL9SX). Licencia **[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/)**. Serie **LIDC-IDRI-1001**, 194 imágenes CT, Siemens Sensation 16, aproximadamente 102 MB, obtenida mediante NCI Imaging Data Commons. UID: `1.3.6.1.4.1.14519.5.2.1.6279.6001.100225287222365663678666836860`. Las figuras y máscaras son derivados didácticos: se han aplicado ventanas, umbrales, submuestreo y suavizado. No se utilizan las anotaciones expertas de nódulos de la colección.
- **Marching cubes:** Lorensen, W. E. y Cline, H. E. (1987). *Marching cubes: A high resolution 3D surface construction algorithm*. SIGGRAPH. [DOI 10.1145/37401.37422](https://doi.org/10.1145/37401.37422).

El fantoma es un maniquí, no un cráneo humano. Las figuras derivadas deben conservar la atribución y el contexto de sus datos. Las series opcionales de IDC tienen sus propias condiciones de uso, que deben revisarse para la colección seleccionada.
''')
md('''
<a id="exportacion"></a>
## Exportación de figuras para diapositivas
La siguiente celda exporta imágenes **PNG con fondo negro y sin ejes**, en `salidas_sipaim/figuras/`: corte crudo, tres ventanas del cráneo, cerebro humano, pulmón del tórax, MPR de fantoma y de tórax, render 3D del fantoma, control de la máscara pulmonar y render 3D de pulmones. Conservamos las proporciones físicas de las MPR.

Plotly conserva la interacción en el notebook. Para el PNG del render usamos **los mismos vértices y triángulos en Matplotlib**, evitando instalar Kaleido u otra dependencia. La cámara y la iluminación pueden diferir del render interactivo. Los PNG son figuras de presentación; no conservan los metadatos DICOM ni sustituyen los volúmenes.
''')
code('''### Exportar todas las figuras clave
Creamos nuevas figuras de fondo negro, sin títulos ni ejes, para su uso en diapositivas. Las mallas se dibujan con `plot_trisurf` y dimensiones físicas. Se espera una lista de diez PNG no vacíos si se ejecutó el bonus pulmonar, además del DICOM y NIfTI guardados anteriormente.''', '''
CARPETA_FIGURAS = SALIDAS / "figuras"  # Organiza los PNG en un subdirectorio propio.
CARPETA_FIGURAS.mkdir(exist_ok=True)  # Crea la carpeta de exportación.
plt.imsave(CARPETA_FIGURAS / "01_craneo_crudo.png", crudo, cmap="gray", vmin=crudo.min(), vmax=crudo.max())  # Exporta el corte crudo sin ejes ni márgenes.
plt.imsave(CARPETA_FIGURAS / "03_torax_pulmon.png", ventana(hu_torax_central, -600, 1500), cmap="gray", vmin=0, vmax=1)  # Exporta el pulmón en su ventana fija.
fig, ejes = plt.subplots(1, 3, figsize=(15, 5), facecolor="black")  # Crea un panel negro de ventanas del cráneo.
for ax, (_, nivel, ancho) in zip(ejes, ventanas_craneo):  # Conserva el orden cerebro, tejido blando y hueso.
    ax.imshow(ventana(hu_craneo, nivel, ancho), cmap="gray", vmin=0, vmax=1)  # Dibuja cada presentación del archivo 18.dcm.
    ax.set_facecolor("black")  # Uniforma el fondo de cada panel.
    ax.axis("off")  # Retira los ejes y marcas.
fig.subplots_adjust(left=0, right=1, bottom=0, top=1, wspace=0.02)  # Reduce márgenes sin perder paneles.
fig.savefig(CARPETA_FIGURAS / "02_craneo_tres_ventanas.png", dpi=200, facecolor="black")  # Guarda el panel completo con fondo negro opaco.
plt.close(fig)  # Libera la figura de exportación.
for volumen, espaciado, nivel, ancho, nombre in [(vol_philips, esp_philips, 400, 1800, "04_mpr_fantoma.png"), (vol_torax, esp_torax, -600, 1500, "05_mpr_torax.png")]:  # Exporta ambas MPR con sus propias escalas.
    fig = mostrar_mpr(volumen, espaciado, nivel, ancho, "")  # Reutiliza el procedimiento de aspecto físico correcto.
    fig.set_facecolor("black")  # Fija el fondo de toda la figura.
    for ax in fig.axes:  # Recorre los tres planos de la MPR.
        ax.set_title("")  # Retira los títulos para las diapositivas.
        ax.set_facecolor("black")  # Mantiene negro el fondo de cada panel.
        ax.axis("off")  # Asegura la ausencia de ejes.
    fig.savefig(CARPETA_FIGURAS / nombre, dpi=200, facecolor="black", bbox_inches="tight")  # Guarda la MPR sin deformar sus proporciones.
    plt.close(fig)  # Libera la figura creada para el archivo.
fig = plt.figure(figsize=(9, 9), facecolor="black")  # Prepara un lienzo negro para el render estático.
ax = fig.add_subplot(111, projection="3d")  # Crea ejes tridimensionales de Matplotlib.
ax.plot_trisurf(vertices[:, 2], vertices[:, 1], vertices[:, 0], triangles=caras, color="ivory", linewidth=0, antialiased=True, shade=True)  # Dibuja exactamente la malla usada en Plotly.
ax.set_box_aspect(np.ptp(vertices[:, [2, 1, 0]], axis=0))  # Conserva las dimensiones físicas de la superficie.
ax.view_init(elev=15, azim=-65)  # Define una cámara oblicua reproducible.
ax.set_facecolor("black")  # Hace negro el fondo de los ejes 3D.
ax.set_axis_off()  # Oculta caja, cuadrícula y marcas de los ejes.
fig.savefig(CARPETA_FIGURAS / "06_render_fantoma.png", dpi=200, facecolor="black", bbox_inches="tight", pad_inches=0)  # Exporta el render sin dependencias adicionales.
plt.close(fig)  # Libera la figura del render.
plt.imsave(CARPETA_FIGURAS / "07_craneo_hueso.png", ventana(hu_craneo, 400, 1800), cmap="gray", vmin=0, vmax=1)  # Añade una ventana ósea individual lista para diapositivas.
plt.imsave(CARPETA_FIGURAS / "08_cerebro_humano.png", ventana(hu_craneo, 40, 80), cmap="gray", vmin=0, vmax=1)  # Exporta el cerebro humano de 18.dcm con ventana cerebral.
if "fig_control_pulmon" in globals():  # Exporta el control visual si se ejecutó el bonus.
    fig_control_pulmon.set_facecolor("black")  # Fija un fondo negro en toda la figura.
    for ax in fig_control_pulmon.axes:  # Recorre las vistas con máscara superpuesta.
        ax.set_title("")  # Retira títulos para las diapositivas.
        ax.set_facecolor("black")  # Mantiene negro el fondo de los paneles.
        ax.axis("off")  # Asegura la ausencia de ejes.
    fig_control_pulmon.savefig(CARPETA_FIGURAS / "09_mascara_pulmones.png", dpi=200, facecolor="black", bbox_inches="tight")  # Guarda el vínculo entre CT y segmentación.
if "vp" in globals() and "cp" in globals():  # Exporta la malla pulmonar cuando existe una segmentación.
    fig = plt.figure(figsize=(9, 9), facecolor="black")  # Prepara un segundo render estático.
    ax = fig.add_subplot(111, projection="3d")  # Crea una vista 3D de los pulmones.
    ax.plot_trisurf(vp[:, 2], vp[:, 1], vp[:, 0], triangles=cp, color="lightskyblue", linewidth=0, antialiased=True, shade=True)  # Dibuja la misma malla que el render interactivo.
    ax.set_box_aspect(np.ptp(vp[:, [2, 1, 0]], axis=0))  # Conserva las proporciones anatómicas.
    ax.view_init(elev=10, azim=-90)  # Presenta una cámara aproximadamente frontal.
    ax.set_facecolor("black")  # Mantiene el fondo negro.
    ax.set_axis_off()  # Oculta la caja y los ejes.
    fig.savefig(CARPETA_FIGURAS / "10_render_pulmones.png", dpi=200, facecolor="black", bbox_inches="tight", pad_inches=0)  # Guarda el render de pulmones para las diapositivas.
    plt.close(fig)  # Libera la figura estática.
for ruta in sorted(CARPETA_FIGURAS.glob("*.png")):  # Enumera los archivos realmente escritos.
    assert ruta.stat().st_size > 0, f"El archivo está vacío: {ruta.name}"  # Comprueba que la exportación produjo contenido.
    print(ruta.name, "—", ruta.stat().st_size, "bytes")  # Informa nombre y tamaño de cada PNG.
print("Descargue la carpeta desde el panel Archivos de Colab:", CARPETA_FIGURAS)  # Indica dónde recuperar las figuras.
''')

md('''
<a id="figuras-ppt"></a>
## Exportar figuras para las diapositivas
Reutilizamos exclusivamente los datos ya cargados del taller: **LIDC-IDRI-1001** para tórax, `hu_craneo` de **GE `18.dcm`** para el control cerebral y, si está disponible, la malla pulmonar `vp`/`cp` del bonus. No se descargan datos, no se releen archivos DICOM y no se instalan dependencias adicionales.

Los dos axiales del tórax usan **el mismo `hu_torax_central`**, correspondiente a `len(vol_torax)//2`: pulmón −600/1500 y mediastino 40/400. El control cerebral usa 40/80. Estas tres imágenes tienen **1000 × 1000 px**. El coronal central usa ventana de pulmón, z invertido y 1000 px de ancho; su altura se calcula con `dz/dx` para conservar la proporción física. Los valores que se muestran con `vmin` y `vmax` siguen expresados en HU, sin normalización a [0,1].

Las imágenes 2D tienen fondo negro y no incluyen ejes, títulos, bordes ni márgenes. El render opcional `torax_pulmones_3d.png` se dibuja con **Matplotlib `plot_trisurf`**, a **1000 × 1000 px**, con superficie celeste y fondo **`#1B2A41`**, sin ejes ni márgenes. Si no existe la malla del bonus, se imprime un aviso y se continúa.

La celda imprime la tabla con dimensiones reales y ventanas, además del índice axial, PixelSpacing, SliceThickness y número de cortes. Reutiliza los metadatos del corte `central_torax` ya leído. Finalmente crea **`figuras_ppt.zip`** con las figuras generadas e inicia su descarga en Colab; fuera de Colab imprime la ruta del ZIP.
''')
code('''### Generar los PNG y descargar el ZIP
Exportamos los HU y la malla que ya existen en memoria, conservando las funciones y las series utilizadas durante el taller. Se espera una tabla con cuatro PNG 2D y, si se ejecutó el bonus, un quinto PNG de pulmones en 3D. Leemos cada PNG guardado para comprobar su tamaño real antes de incorporarlo al ZIP.''', '''
import zipfile  # Comprime las figuras sin añadir dependencias externas.
carpeta_ppt = Path("figuras_ppt")  # Define la carpeta de exportación dentro del directorio actual.
carpeta_ppt.mkdir(exist_ok=True)  # Crea el destino sin modificar las series fuente.
indice_axial_ppt = len(vol_torax) // 2  # Recupera el índice del corte central utilizado en el taller.
dz_ppt, dy_ppt, dx_ppt = esp_torax  # Reutiliza el espaciado físico de LIDC-IDRI en orden z,y,x.
coronal_ppt = vol_torax[::-1, vol_torax.shape[1] // 2, :]  # Extrae el coronal central e invierte z para mostrar arriba la parte superior del cuerpo.
altura_coronal_ppt = max(1, round(1000 * coronal_ppt.shape[0] * dz_ppt / (coronal_ppt.shape[1] * dx_ppt)))  # Calcula la altura en px que conserva la proporción anatómica real.
figuras_2d_ppt = [("torax_pulmon.png", hu_torax_central, -600, 1500, 1000, 1.0), ("torax_mediastino.png", hu_torax_central, 40, 400, 1000, 1.0), ("torax_coronal.png", coronal_ppt, -600, 1500, altura_coronal_ppt, dz_ppt / dx_ppt), ("control_craneo_18.png", hu_craneo, 40, 80, 1000, 1.0)]  # Define los mismos HU axiales para las dos ventanas y reutiliza el control de 18.dcm.
tabla_ppt = []  # Registra únicamente los archivos generados correctamente en esta ejecución.
for nombre, plano, nivel, ancho, altura_px, aspecto in figuras_2d_ppt:  # Recorre las cuatro imágenes 2D solicitadas.
    fig = plt.figure(figsize=(10, altura_px / 100), dpi=100, facecolor="black")  # Fija 1000 px de ancho y la altura requerida a 100 dpi.
    ax = fig.add_axes([0, 0, 1, 1])  # Ocupa el lienzo completo sin márgenes.
    ax.set_facecolor("black")  # Mantiene un fondo negro opaco.
    ax.imshow(ventana(plano, nivel, ancho, normalizar=False), cmap="gray", vmin=nivel - ancho / 2, vmax=nivel + ancho / 2, aspect=aspecto, origin="upper", interpolation="nearest")  # Aplica vmin y vmax sobre los HU recortados, sin normalizarlos.
    ax.axis("off")  # Elimina ejes, bordes y marcas de coordenadas.
    with plt.rc_context({"savefig.bbox": None}):  # Impide que una configuración anterior cambie el tamaño mediante recorte automático.
        fig.savefig(carpeta_ppt / nombre, dpi=100, facecolor="black", edgecolor="none", pad_inches=0, bbox_inches=None, transparent=False)  # Guarda el lienzo completo sin bordes ni márgenes.
    plt.close(fig)  # Libera la figura después de escribir el PNG.
    alto_real, ancho_real = plt.imread(carpeta_ppt / nombre).shape[:2]  # Lee las dimensiones reales del archivo guardado.
    tabla_ppt.append({"Archivo": nombre, "Dimensiones (px)": f"{ancho_real} × {alto_real}", "Ventana (nivel / ancho HU)": f"{nivel} / {ancho}"})  # Añade la ventana y el tamaño verificados a la tabla.
if "vp" in globals() and "cp" in globals():  # Comprueba que se generaron los vértices y caras del bonus pulmonar.
    try:  # Permite continuar con el ZIP si falla la exportación opcional del render.
        fondo_3d_ppt = "#1B2A41"  # Define el fondo especial solicitado para la superficie pulmonar.
        fig = plt.figure(figsize=(10, 10), dpi=100, facecolor=fondo_3d_ppt)  # Crea un lienzo 3D de exactamente 1000 × 1000 px.
        ax = fig.add_axes([0, 0, 1, 1], projection="3d")  # Ocupa todo el lienzo sin márgenes.
        ax.plot_trisurf(vp[:, 2], vp[:, 1], vp[:, 0], triangles=cp, color="lightskyblue", linewidth=0, antialiased=True, shade=True)  # Dibuja directamente la malla pulmonar del bonus en color celeste claro.
        ax.set_box_aspect(np.ptp(vp[:, [2, 1, 0]], axis=0))  # Conserva las dimensiones físicas de la malla en x,y,z.
        ax.view_init(elev=10, azim=-90)  # Selecciona una vista aproximadamente frontal y reproducible.
        ax.set_facecolor(fondo_3d_ppt)  # Mantiene el fondo azul oscuro en el área del render.
        ax.axis("off")  # Oculta caja, ejes, títulos y marcas de coordenadas.
        with plt.rc_context({"savefig.bbox": None}):  # Mantiene el tamaño de salida aunque exista una configuración de recorte previa.
            fig.savefig(carpeta_ppt / "torax_pulmones_3d.png", dpi=100, facecolor=fondo_3d_ppt, edgecolor="none", pad_inches=0, bbox_inches=None, transparent=False)  # Guarda el render sin motores externos ni márgenes.
        plt.close(fig)  # Libera los recursos de la figura 3D.
        alto_real, ancho_real = plt.imread(carpeta_ppt / "torax_pulmones_3d.png").shape[:2]  # Verifica el tamaño real del PNG 3D.
        tabla_ppt.append({"Archivo": "torax_pulmones_3d.png", "Dimensiones (px)": f"{ancho_real} × {alto_real}", "Ventana (nivel / ancho HU)": "No aplica: malla segmentada"})  # Distingue la superficie segmentada de una imagen 2D ventaneada.
    except Exception as error:  # Evita que un problema del render interrumpa las figuras 2D o el ZIP.
        plt.close(fig)  # Libera la figura también cuando falla el render.
        print("Aviso: se omite torax_pulmones_3d.png por un error al dibujar la malla. Detalle:", error)  # Informa la omisión de la figura opcional.
else:  # Permite exportar las figuras principales sin haber ejecutado el bonus.
    print("Aviso: no existe la malla del bonus de pulmones; se omite torax_pulmones_3d.png.")  # Explica por qué no se generó el quinto PNG.
print(pd.DataFrame(tabla_ppt).to_string(index=False))  # Imprime nombre de archivo, dimensiones reales y ventana usada.
print("Índice axial de tórax usado (base 0):", indice_axial_ppt)  # Informa el índice común de las ventanas pulmonar y mediastínica.
print("PixelSpacing del corte (fila, columna), mm:", central_torax.PixelSpacing)  # Reutiliza los metadatos del mismo corte central ya leído.
print("SliceThickness del corte, mm:", central_torax.get("SliceThickness", "No disponible"))  # Informa el grosor real declarado, que puede diferir de dz.
print("Número total de cortes:", len(vol_torax), "Separación medida dz, mm:", dz_ppt)  # Documenta el tamaño y el espaciado del volumen LIDC-IDRI.
ruta_zip_ppt = Path("figuras_ppt.zip").resolve()  # Define la ruta absoluta del paquete solicitado.
with zipfile.ZipFile(ruta_zip_ppt, "w", compression=zipfile.ZIP_DEFLATED) as zip_ppt:  # Regenera el ZIP para esta ejecución.
    for fila in tabla_ppt:  # Incluye solo los PNG actuales, sin incorporar archivos obsoletos de otras ejecuciones.
        zip_ppt.write(carpeta_ppt / fila["Archivo"], arcname="figuras_ppt/" + fila["Archivo"])  # Conserva la carpeta figuras_ppt/ dentro del paquete.
print("ZIP generado:", ruta_zip_ppt)  # Informa dónde quedó guardado el archivo comprimido.
try:  # Permite ejecutar la celda tanto en Colab como en un entorno local.
    from google.colab import files  # Importa la integración de descarga propia de Colab.
    files.download(str(ruta_zip_ppt))  # Inicia la descarga del paquete de figuras al equipo del participante.
except ImportError:  # Contempla la ausencia de Google Colab en una ejecución local.
    print("Fuera de Colab: el ZIP está disponible en", ruta_zip_ppt)  # Proporciona la ruta para recuperar el archivo manualmente.
''')

notebook = dict(cells=cells, metadata={"colab": {"name": "SIPAIM_2026_DICOM_Python.ipynb", "provenance": []}, "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python", "version": "3.12"}}, nbformat=4, nbformat_minor=5)
archivo_notebook = Path("SIPAIM_2026_DICOM_Python.ipynb")
ids_existentes = {}
if archivo_notebook.exists():
    celdas_existentes = json.loads(archivo_notebook.read_text(encoding="utf-8"))["cells"]
    ids_existentes = {(c["cell_type"], "".join(c["source"])): c["id"] for c in celdas_existentes}
for index, cell in enumerate(cells):
    cell["id"] = ids_existentes.get((cell["cell_type"], cell["source"]), f"sipaim-nueva-{index:03d}")
    cell["source"] = cell["source"].splitlines(keepends=True)
Path("SIPAIM_2026_DICOM_Python.ipynb").write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Notebook generado: {len(cells)} celdas, {sum(c['cell_type'] == 'code' for c in cells)} de código.")
