# Registros operativos

El sistema deja de registrar automáticamente consultas SQL y sus parámetros.
Los loggers `django.db`, `django.db.backends` y `django.db.backends.schema` usan
un destino nulo y no propagan mensajes, incluso con un cursor de depuración.
Los errores y avisos de la aplicación siguen disponibles por consola.
Esto no anonimiza todo traceback: los registros operativos deben seguir siendo
privados, porque una excepción puede incluir detalles de un registro o petición.

## Desarrollo con Docker

```powershell
git pull --ff-only origin dev
docker compose up --build -d
docker compose logs --tail 100 web
```

Compose limita los registros de cada contenedor a tres archivos de 10 MB usando
el driver `json-file`. La configuración se aplica al recrear los contenedores;
no cambia ni elimina los volúmenes de PostgreSQL o archivos adjuntos.
La retención de los logs antiguos de un contenedor recreado no es un respaldo.

## Archivo opcional fuera de Docker

La consola es el destino predeterminado. Para habilitar además un archivo,
configurar `IVEM_LOG_FILE` con una ruta absoluta, por ejemplo
`/var/log/ivem/application.log`, en el entorno del servicio y reiniciarlo.
Crear previamente el directorio, con permisos limitados al usuario del servicio
y al personal autorizado. No colocar el archivo dentro de una carpeta pública.

El archivo rota a 5 MiB y conserva cinco respaldos, además del archivo activo.
No usar un mismo archivo rotativo con varios procesos: en un despliegue con
múltiples workers, preferir consola y un recolector de registros externo con
rotación, o destinos separados por proceso. Django no puede coordinar la rotación
entre procesos con este handler.

## Log SQL histórico

`django_db.log` deja de estar seguido por Git. El archivo de este workspace se
conserva localmente; `.gitignore` y `.dockerignore` excluyen `*.log` y sus respaldos.

**Antes de actualizar otra instalación**, si necesita conservar el log viejo,
respaldarlo fuera del repositorio: un `git pull` puede eliminar un archivo que
antes estaba seguido y ahora se retira. Si tiene cambios locales, Git puede
pedir resolverlos. Esto no afecta los oficios o archivos PDF.

El contenido anterior **permanece en commits antiguos**. Revisar privadamente
si contiene datos personales o secretos, restringir acceso al repositorio y
coordinar la eventual limpieza del historial con sus colaboradores. No se hizo
un force push ni se reescribieron commits. Rotar credenciales solo según lo que
haya quedado expuesto, usando un procedimiento de cambio controlado.

Esta entrega no aplica migraciones ni modifica datos de la base.
