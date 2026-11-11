# Actualización de Django y librerías — 9 de noviembre de 2026

Se actualiza la instalación de Python manteniendo Django en la rama **5.2 LTS**.
La combinación está fijada en `requirements.txt` y probada con **Python 3.12**,
PostgreSQL 17 y Redis 7.4. No se modifican lógica de negocio, modelos, tablas
anuales, archivos adjuntos, paleta ni formato de impresión.

## Versiones

| Paquete | Antes | Después |
| --- | --- | --- |
| asgiref | 3.8.1 | 3.13.0 |
| Django | 5.1 | 5.2.19 |
| django-admin-interface | 0.28.8 | 0.32.0 |
| django-ckeditor | 6.7.1 | 6.7.4 |
| django-colorfield | 0.11.0 | 0.14.0 |
| django-jazzmin | 3.0.0 | 3.0.5 |
| django-js-asset | 2.2.0 | 5.0.0 |
| narwhals | 1.35.0 | 2.28.0 |
| numpy | 2.2.5 | 2.5.4 |
| packaging | 25.0 | 26.3 |
| pandas | 2.2.3 | 3.1.1 |
| pillow | 10.4.0 | 13.0.0 |
| plotly | 6.0.1 | 7.1.0 |
| psycopg2-binary | 2.9.10 | 2.9.13 |
| pypdf | 6.21.4 | 7.0.0 |
| python-dateutil | 2.9.0.post0 | 4.0.0 |
| python-dotenv | 1.1.0 | 1.2.4 |
| pytz | 2025.2 | 2026.6 |
| sqlparse | 0.5.1 | 0.6.1 |
| tzdata | 2024.1 | 2026.6 |

Las dependencias que ya coincidían con la versión compatible resuelta se
conservan. Se mantienen los paquetes de interfaz/editor que estaban declarados;
esta entrega no activa módulos nuevos ni cambia la interfaz del administrador.

## Resultado de compatibilidad

- Instalación desde cero en un entorno virtual aislado: correcta.
- **88 pruebas aprobadas** con la combinación nueva, incluyendo concurrencia,
  archivos, permisos, login, apariencia y conservación de folios.
- Ejecución con advertencias de Python habilitadas: no se observaron avisos de
  deprecación durante la suite. Los errores 500 simulados de las pruebas de
  páginas públicas son esperados y esas pruebas pasan.
- Imagen Docker construida desde requirements actualizado: correcta. La suite
  completa también pasó dentro del contenedor, con PostgreSQL y Redis aislados.
- Chromium: login real, gráficas Plotly renderizadas, apariencia, administrador
  y página 404; sin errores JavaScript. Datos ficticios en un proyecto Docker
  separado. El primer intento del navegador apuntó localhost al proxy externo;
  se corrigió el bypass de loopback en la herramienta de prueba, sin cambios
  en la aplicación.
- `pip check`: sin incompatibilidades declaradas.
- `makemigrations --check --dry-run`: sin cambios de modelos.
- `migrate --plan` en desarrollo existente: ninguna operación pendiente.
- Las huellas de registros y secuencias de la DB local coinciden antes/después.

No se detectaron errores de compatibilidad que requirieran modificar código de
la aplicación en la suite. Esto no garantiza cobertura de todo escenario real.
Pandas, Plotly, Pillow y pypdf cambiaron de versión mayor: revisar también los
flujos con documentos y volúmenes representativos del entorno operativo.

## Dependencias y asuntos pendientes

pip-audit consultó **25 distribuciones**, sin paquetes omitidos y **sin avisos
conocidos** para estas versiones en la fecha del análisis. El inventario completo
instalado coincide con los paquetes fijados; no se usó el entorno de las
herramientas de auditoría para construir requirements de ejecución.
El JSON adjunto conserva el resultado. Ausencia de avisos conocidos no prueba
seguridad absoluta; repetir el análisis periódicamente.

El informe anterior conserva los hallazgos históricos para las versiones viejas.
Permanecen fuera de esta actualización: log SQL versionado, configuración de
clave/hosts/TLS de producción, permisos amplios de staff y restricciones de DB.
No se cambiaron para evitar mezclar la actualización con cambios funcionales.

## Actualizar desarrollo local

Desde el repositorio en la rama `dev`, con Docker Desktop activo:

```powershell
git pull --ff-only origin dev
docker compose up --build -d
docker compose exec -T web python -m django --version
docker compose exec -T web python -m pip check
docker compose exec -T web python manage.py test --noinput
```

El primer build descarga versiones nuevas. Los volúmenes existentes de PostgreSQL
y archivos se conservan. No ejecutar `down -v` ni borrar datos para actualizar.

Si se trabaja sin Docker, usar Python 3.12 y un entorno virtual nuevo, instalar
`requirements.txt`, configurar PostgreSQL y Redis y ejecutar las mismas
comprobaciones. No reutilizar ciegamente el entorno antiguo para validar la
instalación limpia.

## Producción y reversión

Esta entrega solo se publica en la rama `dev`, no se despliega en producción.
Antes de producción: respaldar PostgreSQL y MEDIA_ROOT, probar sobre una copia,
revisar `migrate --plan` y conservar la imagen/entorno anterior. La prueba local
sin migraciones pendientes no demuestra el estado de la DB de producción.

Como esta actualización no añade migraciones, una reversión de dependencias
consiste en recuperar la imagen o entorno anterior y reiniciar el servicio,
conservando los volúmenes. Evitar reinstalar versiones viejas encima del entorno
nuevo: reconstruir desde el commit anterior. Las dependencias anteriores tienen
avisos de seguridad y la reversión sería solo una recuperación temporal.
