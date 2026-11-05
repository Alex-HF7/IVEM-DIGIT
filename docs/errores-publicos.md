# Páginas públicas de error

La app muestra una pantalla común para errores 400, 403, 404, 405, 413, 429,
500 y 503. Las respuestas conservan su código HTTP y encabezados útiles como
`Allow` y `Retry-After`. La página usa el estilo del sistema, una animación CSS
compatible con movimiento reducido y un enlace para volver al inicio.

Las páginas no incluyen rutas disponibles, consultas, variables, mensajes de
excepción ni trazas. No usan la plantilla base ni procesadores de contexto que
consultan la base de datos, y no necesitan CDN, JavaScript ni archivos estáticos.
Los detalles técnicos permanecen en los logs del servidor.
Las respuestas JSON existentes mantienen su formato para no romper los formularios;
los errores generales de solicitudes AJAX reciben un mensaje JSON público.

## Desarrollo local

`DEBUG` queda desactivado por defecto también en Docker. El comando de Compose
usa `runserver --insecure` exclusivamente para servir los archivos estáticos de
desarrollo con `DEBUG=False`; no es una configuración de producción.

```powershell
git pull --ff-only origin dev
docker compose up --build -d
```

Comprobar una ruta inexistente, por ejemplo `/swagger/`, y verificar que el
listado y las imágenes sigan cargando. Las rutas que simulan fallos para las
pruebas están en un URLconf separado y no se publican en la aplicación.

## Producción

Mantener `IVEM_DEBUG` sin definir o con valor `false`. No activar depuración en
producción. El middleware también reemplaza pantallas HTML técnicas si se
activa por error, pero eso no sustituye una configuración de despliegue segura.
Nginx debe seguir sirviendo `/static/`; no se debe utilizar `runserver` en producción.

Esta entrega cubre los errores que llegan a Django. Las páginas que genera Nginx
por sí mismo (por ejemplo, si Gunicorn no responde o Nginx rechaza un archivo por
su tamaño) requieren revisar su configuración en el servidor. No se ha modificado
Nginx ni la base de datos.
