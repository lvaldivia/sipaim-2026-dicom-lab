# DICOM Lab · SIPAIM 2026

Aplicación educativa desplegada con el perfil **luisvaldivia**, región **us-east-1**.

**URL:** https://dzij5ey0xgf92.cloudfront.net

La aplicación abre directamente, sin código de acceso ni pantalla de inicio de sesión. Las credenciales AWS permanecen en el backend. La URL de origen Lambda continúa protegida mediante AWS_IAM y CloudFront OAC; el acceso público al laboratorio se realiza a través de CloudFront.

## Funcionalidad

- Tres estudios públicos del notebook: tórax LIDC-IDRI-1001 (194 cortes), cerebro/cráneo GE (28 cortes) y fantoma Philips (140 cortes).
- Navegación axial, ventanas de cerebro, pulmón, mediastino, tejido blando y hueso; nivel/ancho ajustables.
- MPR coronal y sagital con escala física y eje z invertido. Las MPR de GE están desactivadas por su inclinación y separación irregular.
- Medición de HU al hacer clic, calculada sobre la matriz original; descarga del PNG visible.
- Preguntas sobre el corte visible con Amazon Nova Lite a través de Bedrock. Respuestas en español/inglés mediante selector o petición explícita.
- Conversación con memoria de los últimos seis pares de turnos. Botones «Más sencillo», «Pregúntame», «Profundizar» y «Escuchar» tras cada explicación. El tutor puede hacer una pregunta y comentar la respuesta siguiente.
- Se pueden enviar hasta tres preguntas adicionales mientras llega una respuesta: se muestran en cola y se procesan en orden, sin descartar mensajes silenciosamente. Se incluyen controles para detener, reintentar y comenzar una nueva conversación. Una espera superior a 60 segundos permite reintentar en lugar de dejar bloqueado el chat.
- Audio MP3 con Polly: Lupe/es-US y Joanna/en-US. El idioma del audio es independiente; cuando cambia respecto del texto, Bedrock traduce la explicación antes de sintetizarla.
- Importación de un ZIP de CT anonimizada mediante S3 firmado. Se selecciona la serie CT más numerosa y se exige geometría axial regular. Se conservan solo intensidades y atributos técnicos en el volumen derivado. Límites: 150 MB de ZIP, 512 MB descomprimidos, 1000 entradas, 32 MB por instancia, matriz máxima de 1024 × 1024, 600 cortes y 64 millones de píxeles en la serie elegida.
- Importaciones disponibles durante un máximo de 24 h en la aplicación. S3 elimina sus objetos mediante ciclo de vida de un día, cuya ejecución no es instantánea al cumplirse la hora. El ZIP fuente se elimina inmediatamente tras la importación correcta; los ZIP fallidos caducan por el ciclo de vida.

## Arquitectura y acceso

CloudFront sirve el frontend HTML/JS desde S3 privado y enruta `/api/*` a Lambda Python 3.12. Los dos orígenes utilizan OAC/SigV4; la URL directa de Lambda exige AWS_IAM. Los POST añaden `x-amz-content-sha256` del cuerpo enviado. La aplicación no exige una clave adicional.

La función utiliza 2048 MB, máximo 90 segundos y concurrencia reservada de 3. Su rol permite leer las series del bucket de este proyecto, gestionar únicamente sus cargas/importaciones, invocar Nova Lite y sintetizar voz en Polly. Los logs se conservan 7 días; no se registran cuerpos de preguntas ni contenido DICOM. Las respuestas no se almacenan en el servidor.

Es un **prototipo educativo**, sin validación para diagnóstico ni uso clínico. Utilice datos públicos o anonimizados. La supresión de metadatos identificativos en la importación no elimina posibles textos incrustados en píxeles ni certifica anonimización. El asistente observa el corte seleccionado, no revisa automáticamente el estudio completo. Las mediciones provienen de Python; las explicaciones generativas pueden ser incorrectas.

El despliegue genera cargos por uso de Bedrock, Polly, Lambda, CloudFront, registros y almacenamiento S3. No se ha contratado capacidad provisionada ni creado una GPU.

## Reproducir y actualizar

Desde la carpeta DICOM y el entorno `.venv`:

```powershell
.\.venv\Scripts\python app/prepare_data.py
.\.venv\Scripts\python -m pip install --target app/.build/package --platform manylinux_2_28_x86_64 --platform manylinux2014_x86_64 --python-version 3.12 --implementation cp --only-binary :all: --no-compile numpy pydicom Pillow
.\.venv\Scripts\python app/deploy.py
```

`deploy.py` usa el perfil autorizado, publica archivos y aplica `cloudformation.json` al stack **sipaim-dicom-lab**. El bucket del proyecto se gestiona fuera del stack y contiene el paquete Lambda, frontend y series; no se modifica ningún recurso de otros proyectos. Las salidas públicas se guardan en `deployment.json`. No añada `.private/`, `.build/`, `.test-tools/` ni `data/` al repositorio.

Para detener los recursos del proyecto, elimine el stack `sipaim-dicom-lab` en CloudFormation y, cuando termine, vacíe y elimine únicamente el bucket indicado en `deployment.json`. No se ha ejecutado esa eliminación.

## Verificación

```powershell
.\.venv\Scripts\python -m pytest app/tests -q
node --check app/frontend/app.js
node --test app/tests/chat-ui.test.cjs
.\.venv\Scripts\python app/smoke_test.py
```

Las diez pruebas Python verifican calibración/ventaneo, geometría MPR, bloqueo de GE inclinado, acceso directo, mediciones, seis parejas de historial, espera de la respuesta del alumno sin inventar turnos y rechazo de consultas sobre importaciones caducadas. La prueba de interfaz usa un DOM aislado con jsdom (dependencia solo de desarrollo en `.test-tools/`) para comprobar envío consecutivo, cola, contexto del siguiente turno, acciones de seguimiento, recuperación de errores y cancelación. No controla un navegador real. La prueba de integración hace **21 controles reales contra la URL de CloudFront**, incluyendo una conversación de práctica con seguimiento, Bedrock con imagen en español/inglés, MP3 en ambos idiomas, traducción para audio y carga/importación de seis cortes del fantoma público. Los resultados están en `.build/smoke-result.json`; los MP3 de prueba no se publican.

La simulación local de errores de proveedores está en `postman/simulations/`. El CLI de Postman no pudo iniciar su daemon local por un fallo TLS; no se afirma que esa simulación haya pasado. Su contexto documenta la limitación. Las llamadas reales de éxito sí fueron comprobadas. El control de Google Chrome fue rechazado por permisos del entorno: queda pendiente la revisión visual y de reproducción interactiva en navegador.

El contrato HTTP está en `api.openapi.json`. Los errores de proveedores se muestran como errores recuperables, sin inventar respuestas ni audio.

## Créditos

- [LIDC-IDRI / TCIA](https://doi.org/10.7937/K9/TCIA.2015.LO9QL9SX): Armato III y colaboradores, licencia CC BY 3.0. Serie LIDC-IDRI-1001.
- [dcm_qa_ct](https://github.com/neurolabusc/dcm_qa_ct): Chris Rorden, BSD-2-Clause. GE cortesía de Aliza Medical Imaging; fantoma Philips cortesía de P. Morgan, Nottingham.

Se mantienen las intensidades HU; PNG, ventanas y reconstrucciones son derivados educativos. El notebook original permanece disponible para descarga desde la aplicación.
