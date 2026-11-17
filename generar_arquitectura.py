"""Genera un diagrama técnico 16:9 en PNG 4K y SVG para las diapositivas."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle

DESTINO = Path(__file__).resolve().parent / "docs/arquitectura"
DESTINO.mkdir(parents=True, exist_ok=True)
FONDO, TARJETA, BORDE = "#1B2A41", "#24364F", "#445570"
BLANCO, GRIS, NARANJA, AZUL, VIOLETA = "#F3F6FF", "#BCC8DD", "#FFAD4B", "#8FD6FB", "#BEABFF"
plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none"})
fig = plt.figure(figsize=(16, 9), dpi=240, facecolor=FONDO)
ax = fig.add_axes([0, 0, 1, 1])
ax.set(xlim=(0, 16), ylim=(0, 9))
ax.axis("off")

def texto(x, y, contenido, size=11, color=BLANCO, **kwargs):
    return ax.text(x, y, contenido, fontsize=size, color=color, va="center", **kwargs)

def tarjeta(x, y, w, h, titulo, subtitulo, color, etiqueta=None):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.015,rounding_size=0.14", facecolor=TARJETA, edgecolor=BORDE, linewidth=1.1))
    ax.plot([x + .19, x + .19], [y + .21, y + h - .21], color=color, linewidth=3.4, solid_capstyle="round")
    if etiqueta:
        texto(x + .37, y + h - .26, etiqueta, 7.4, color, weight="bold")
    texto(x + .37, y + h - (.58 if etiqueta else .42), titulo, 13, BLANCO, weight="bold")
    texto(x + .37, y + .37, subtitulo, 9.3, GRIS, linespacing=1.6)

def flecha(puntos, color=GRIS, label=None, label_xy=None, discontinua=False, doble=False):
    for inicio, fin in zip(puntos[:-2], puntos[1:-1]):
        ax.plot([inicio[0], fin[0]], [inicio[1], fin[1]], color=color, linewidth=1.5, linestyle="--" if discontinua else "-", zorder=1)
    ax.add_patch(FancyArrowPatch(puntos[-2], puntos[-1], arrowstyle="<->" if doble else "-|>", mutation_scale=13, linewidth=1.5, color=color, linestyle="--" if discontinua else "-", zorder=1))
    if label and label_xy:
        texto(*label_xy, label, 8.4, color, ha="center", bbox={"facecolor": FONDO, "edgecolor": "none", "pad": 2.5})

texto(.65, 8.38, "DICOM Lab", 29, weight="bold")
texto(3.44, 8.35, "SIPAIM 2026", 12, AZUL, weight="bold")
texto(.67, 7.86, "De la imagen médica a una explicación que puedes escuchar", 15, GRIS)
ax.plot([.65, 15.35], [7.47, 7.47], color=BORDE, linewidth=.7)

# El contenedor representa la cuenta AWS; el navegador permanece fuera.
ax.add_patch(FancyBboxPatch((3.62, 1.12), 11.78, 5.97, boxstyle="round,pad=0.02,rounding_size=.18", edgecolor="#5C6D86", facecolor="none", linewidth=1, linestyle=(0, (5, 4))))
texto(3.9, 6.82, "AWS  /  us-east-1", 10, NARANJA, weight="bold")

tarjeta(.65, 3.62, 2.37, 2.02, "Navegador", "Visor DICOM + MPR\nChat en español / inglés\nAudio y descarga MP3", AZUL, "APLICACIÓN WEB")
texto(.78, 3.14, "Acceso directo\nsin código de entrada", 9.2, GRIS, linespacing=1.5)

tarjeta(4.0, 4.04, 2.65, 1.43, "CloudFront", "HTTPS + enrutamiento", NARANJA, "PUNTO DE ENTRADA")
tarjeta(4.0, 1.69, 2.65, 1.42, "Amazon S3", "Frontend HTML / CSS / JS", NARANJA, "SITIO PRIVADO")
tarjeta(7.85, 4.04, 3.02, 1.43, "AWS Lambda", "Python · pydicom · NumPy", NARANJA, "LECTOR Y API")
tarjeta(7.85, 1.69, 3.02, 1.42, "Amazon S3", "Series CT + cargas temporales", NARANJA, "DATOS PRIVADOS")
tarjeta(12.0, 5.14, 2.93, 1.43, "Amazon Bedrock", "Nova Lite · imagen + contexto", VIOLETA, "EXPLICACIÓN BILINGÜE")
tarjeta(12.0, 3.17, 2.93, 1.43, "Amazon Polly", "Lupe (ES) · Joanna (EN)", VIOLETA, "SÍNTESIS DE VOZ")
tarjeta(12.0, 1.45, 2.93, 1.17, "CloudWatch", "Logs técnicos · 7 días", GRIS)

flecha([(3.03, 4.77), (3.98, 4.77)], AZUL, "HTTPS", (3.5, 5.04), doble=True)
flecha([(6.67, 4.77), (7.83, 4.77)], AZUL, "/api/*", (7.23, 5.04), doble=True)
flecha([(5.31, 4.01), (5.31, 3.13)], GRIS, "Frontend", (5.94, 3.58), doble=True)
flecha([(9.35, 4.01), (9.35, 3.13)], GRIS, "HU + metadatos", (10.28, 3.57), doble=True)
flecha([(10.89, 5.03), (11.45, 5.03), (11.45, 5.85), (11.98, 5.85)], VIOLETA)
texto(9.43, 5.94, "PNG del corte visible\n+ datos medidos + historial", 8.7, VIOLETA, ha="center", linespacing=1.5)
flecha([(10.89, 4.47), (11.43, 4.47), (11.43, 3.87), (11.98, 3.87)], VIOLETA)
texto(11.43, 3.3, "Texto → MP3", 8.1, VIOLETA, ha="center", rotation=90)
flecha([(10.89, 4.15), (11.15, 4.15), (11.15, 2.02), (11.98, 2.02)], GRIS, discontinua=True)

# La explicación y el audio regresan al usuario a través de Lambda y CloudFront.
flecha([(12.93, 6.6), (12.93, 7.19), (2.15, 7.19), (2.15, 5.68)], AZUL, "RESPUESTA + AUDIO  ·  vía Lambda y CloudFront", (7.76, 7.19))
texto(4.03, 6.13, "CloudFront autentica el acceso a los orígenes con OAC / SigV4", 8.2, GRIS)

ax.plot([.65, 15.35], [.88, .88], color=BORDE, linewidth=.7)
texto(.67, .49, "DATOS:  LIDC-IDRI-1001  ·  CT cerebral GE  ·  Fantoma Philips", 9, GRIS)
texto(15.33, .49, "Uso educativo · sin diagnóstico clínico", 9, AZUL, ha="right")

for extension in ("png", "svg"):
    fig.savefig(DESTINO / f"arquitectura-dicom-lab.{extension}", dpi=240, facecolor=FONDO, pad_inches=0, bbox_inches=None)
svg = DESTINO / "arquitectura-dicom-lab.svg"
svg.write_text("\n".join(linea.rstrip() for linea in svg.read_text(encoding="utf-8").splitlines()) + "\n", encoding="utf-8")
plt.close(fig)
print(DESTINO / "arquitectura-dicom-lab.png")
print("PNG 3840 × 2160 px · formato 16:9 · SVG editable incluido.")
