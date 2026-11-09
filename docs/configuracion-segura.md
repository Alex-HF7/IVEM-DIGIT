# Clave privada y hosts del servidor

Se separan los módulos de configuración para que desarrollo no herede una clave
compartida de producción:

- `ivem_digit.settings_base`: opciones comunes; no es un módulo de arranque.
- `ivem_digit.settings`: servidor, exige clave y hosts explícitos.
- `ivem_digit.settings_local`: desarrollo, usado por Docker Compose.

No se modifica PostgreSQL ni se añaden migraciones. Cambiar la clave no borra
usuarios, contraseñas, archivos ni folios; sí puede invalidar sesiones y valores
firmados anteriormente. Esta entrega no se despliega en producción.

## Desarrollo con Docker

```powershell
git pull --ff-only origin dev
docker compose up --build -d
```

No se requiere editar `.env` para arrancar. Si no se proporciona IVEM_SECRET_KEY,
se genera una clave aleatoria privada, que se conserva en el nuevo volumen
`development_settings` y se reutiliza en arranques posteriores. Es independiente
de los volúmenes existentes de DB y PDF. No borrar el volumen para resolver
problemas de acceso; revisar los mensajes y permisos del servicio.

La primera actualización desde la clave antigua puede requerir iniciar sesión
de nuevo. No cambia la contraseña de ninguna cuenta. Si ya se configuró una
clave privada fuerte mediante IVEM_SECRET_KEY, se sigue usando esa clave.

El acceso local admite `localhost`, `127.0.0.1` e IPv6 loopback; `testserver` se
reserva para pruebas. No acepta hosts arbitrarios ni expone Docker a la red.
Para compartir el sistema fuera del equipo, configurar un despliegue separado;
no añadir `*` ni usar la configuración local en producción.

Sin Docker, activar el entorno Python y seleccionar explícitamente el módulo:

```powershell
$env:DJANGO_SETTINGS_MODULE = "ivem_digit.settings_local"
python manage.py check
python manage.py runserver
```

La clave se conserva en `.local/secret-key`, ignorada por Git y Docker. El archivo
se crea con permisos 0600 en sistemas POSIX. Una clave existente inválida no se
reemplaza silenciosamente. La publicación inicial del archivo es atómica para
que varios arranques usen el mismo valor.

## Preparar producción antes de actualizar

**No desplegar esta versión en el servidor sin configurar primero estas variables**:

- `IVEM_SECRET_KEY`: clave aleatoria de al menos 50 caracteres, sin el prefijo
  `django-insecure-`. No debe ser un valor repetitivo, publicado o compartido.
- `IVEM_ALLOWED_HOSTS`: IP pública real y/o nombres exactos del servidor,
  separados por comas. Por ejemplo `203.0.113.10,ivem.example.com` son ejemplos
  de documentación, no direcciones para copiar en una instalación real.

Se rechazan clave ausente/corta, hosts vacíos, `*`, subdominios comodín,
protocolos, puertos y rutas. El sistema falla al iniciar con un mensaje que
identifica la variable incorrecta, sin imprimir la clave.

Generar una clave en una terminal privada del servidor, por ejemplo:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Guardar el resultado en el gestor de secretos o entorno privado del servicio.
No pegarlo en chats, commits, capturas o archivos de ejemplo. Si se usa `.env`,
restringir sus permisos y mantenerlo fuera del repositorio. Puede usarse
`.env.example` como guía de los nombres de variables, no como configuración final.

Si producción ya usa una clave privada fuerte, conservar exactamente ese valor
para evitar cierres de sesión. Si usa la clave antigua publicada, programar su
rotación y el nuevo inicio de sesión de los usuarios. No conservar la clave
publicada como SECRET_KEY_FALLBACKS para evitar el cierre de sesión: prolongaría
su aceptación. Revisar otros datos firmados que dependan de ella.

Antes de reiniciar, usar el entorno del servicio para ejecutar:

```bash
python manage.py check --deploy
python manage.py migrate --plan
```

El comando de comprobación no imprime la clave. Una ejecución local no demuestra
que las variables del servicio WSGI/ASGI estén configuradas: verificarlas en su
propio entorno de arranque. Los avisos de HTTPS, HSTS y cookies requieren revisar
Nginx/TLS; esta entrega no los activa sin conocer el servidor. Django continúa
escuchando mediante su proxy según la configuración existente.

La lista de hosts valida la cabecera Host; no es un firewall ni limita por sí
sola qué redes pueden conectarse. Mantener el control de red empresarial en
Nginx/firewall/VPN según el despliegue.

## Validación de esta entrega

95 pruebas aprobadas en el entorno local y dentro de Docker. Se probaron claves
inválidas, configuración ausente, hosts inesperados y creación concurrente de la
clave local. Un valor firmado siguió siendo válido tras recrear el contenedor
con su volumen de configuración. En HTTP local, login respondió 200 y un Host
no autorizado respondió 400. No se añadieron migraciones.
