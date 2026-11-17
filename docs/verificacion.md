# Verificación realizada

La aplicación desplegada en https://dzij5ey0xgf92.cloudfront.net fue comprobada con el perfil AWS autorizado `luisvaldivia`, en CPU. Las pruebas no equivalen a una validación clínica.

| Capa | Evidencia | Alcance |
|---|---|---|
| Notebook | 82 celdas; 34 bloques de código con sintaxis válida, explicación previa y comentarios; 8 enlaces del índice | Validación estática; las Partes 1 a 4 se conservaron durante la revisión de exportación |
| Procesamiento | Ejecución local de las celdas científicas sobre GE, Philips y LIDC-IDRI | HU, histogramas, MPR, mallas, copia DICOM y NIfTI comprobados |
| Exportación PPT | Cinco PNG y contenido del ZIP verificados | Tres axiales/control y render a 1000 × 1000; coronal a 1000 × 1058; relaciones físicas conservadas |
| Python | 10 pruebas de pytest | Ventana sin mutar HU, proporción y giro de MPR, geometría GE, acceso directo, medición, idiomas, historial, caducidad y espera del alumno |
| Interfaz | 1 prueba Node/jsdom con múltiples pasos | Acceso sin código, envío en cola, historial correcto, acciones, fallo de red, reintento, detener y nueva conversación |
| Servicios desplegados | 21 controles HTTP reales desde CloudFront | Imágenes, medidas, chat multimodal, práctica de varios turnos, inglés/español, MP3 y carga/importación del fantoma |

Los 21 controles reales incluyeron:

1. Frontend HTTPS.
2. Acceso directo sin código.
3. Sesión de compatibilidad sin contraseña.
4. Disponibilidad de las tres series públicas.
5. PNG axial de tórax.
6. PNG axial de GE.
7. PNG axial del fantoma.
8. Rechazo de MPR para GE inclinado.
9. MPR torácica con aspecto físico correcto.
10. HU medidos iguales al volumen original.
11. Bedrock con imagen en español.
12. Pregunta del tutor sin adelantar ni inventar la respuesta del alumno.
13. Respuesta al siguiente turno usando el historial.
14. Petición explícita de inglés que prevalece sobre el selector.
15. MP3 español real.
16. MP3 inglés real.
17. Traducción para audio en idioma distinto del texto.
18. Rechazo de una pregunta vacía.
19. Carga S3 firmada de un ZIP del fantoma público.
20. Importación real de seis cortes DICOM.
21. Ausencia de identificadores de paciente en los metadatos derivados.

## Límites conocidos

- No se controló Chrome: el entorno rechazó el permiso de automatización. La prueba DOM no sustituye revisión visual, accesibilidad completa o reproducción de audio en un navegador real.
- La simulación Postman se intentó dos veces y no pudo iniciar su daemon por un fallo TLS local. No se afirma que esa simulación haya pasado. Su contexto se conserva en `app/postman/simulations/`.
- Las pruebas reales crean peticiones facturables y una importación temporal del fantoma; por ese motivo no forman parte de GitHub Actions.
- El montaje de Drive y la interfaz interactiva de Colab deben revisarse en una sesión real antes del evento.
- El modelo generativo no está validado para detectar enfermedades ni para interpretar estudios clínicos completos.
