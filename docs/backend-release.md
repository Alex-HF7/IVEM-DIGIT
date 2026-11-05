# Correcciones del backend sin migración de datos

Esta entrega conserva las tablas anuales, folios, secuencias y rutas de PDF existentes.
No incluye migraciones de Django ni cambios de restricciones, índices o tablas.
No ejecutar `makemigrations` para desplegar esta entrega: la revisión del
administrador dinámico y su relación con las migraciones queda para otra fase.

## Acceso aplicado en Django

- Personal con `is_staff` o superusuario: ambos departamentos, pendientes,
  asignación de folio y eliminación lógica mediante POST.
- Grupo `UCG`: lectura, registro, edición de pendientes y archivos de UCG.
- Grupo `Delegacion`: las mismas funciones en Delegación.
- Otros usuarios: no reciben acceso a documentos por el solo hecho de iniciar sesión.

Antes de desplegar, revisar las membresías existentes en el administrador.
La entrega no asigna grupos ni cambia usuarios automáticamente.
Los oficios con folio no admiten edición ni reemplazo de PDF. Se conserva la
posibilidad de cargar su primer PDF si aún no tienen archivo.
Las fechas no forman parte de los campos editables.

## PDF y conservación de archivos

Los nuevos PDF se validan con `pypdf`, con el límite configurado en `IVEM_PDF_MAX_MB`.
Se requieren documentos legibles, con páginas y sin contraseña.
La validación no recorre ni transforma los archivos históricos.
Cada nueva carga usa un nombre único. El reemplazo actualiza la referencia
bajo bloqueo de fila y conserva el anterior hasta confirmar la transacción.
Si falla la actualización, se limpia el nuevo y se conserva el anterior.
Si falla la limpieza del anterior después del commit, se registra el fallo;
la referencia sigue apuntando al PDF nuevo.

## Despliegue de producción

1. Respaldar PostgreSQL y el directorio de archivos adjuntos antes de actualizar.
2. Verificar los grupos de los usuarios que van a operar el sistema.
3. Instalar `requirements.txt`, que incorpora `pypdf==6.21.4`, y reiniciar el
   servicio Django/Gunicorn usando el procedimiento del servidor.
4. **Revisar Nginx:** las solicitudes a la ruta de `MEDIA_URL` (por defecto `/media/`)
   deben pasar por Django. Si hay un `alias` o `root` que entrega esos PDF
   directamente, seguirá evitando los permisos del backend y debe sustituirse
   por el proxy al mismo upstream de Django. Mantener el servicio de `/static/`.
   No se ha modificado ni validado la configuración del Nginx de producción.
5. Comprobar inicio de sesión, lectura de un PDF antiguo, permisos por
   departamento y operaciones sobre registros de prueba.

Las restricciones nuevas de la base, los índices, la unificación de tablas y la
configuración de seguridad de producción quedan fuera de esta entrega.

## Comprobación local

```powershell
git pull --ff-only origin dev
docker compose up --build -d
docker compose exec web python manage.py test documento
```

Las pruebas usan una base temporal y directorios temporales para los PDF.
No usar `docker compose down -v`: elimina los volúmenes con los datos locales.
