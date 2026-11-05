# Acceso al sistema: diseño y protección de intentos

## Qué cambia

- Pantalla adaptable con la paleta del sistema, campos identificados, opción de
  mostrar/ocultar la contraseña y aviso de bloqueo de mayúsculas.
- Compatibilidad con gestores de contraseñas. La contraseña nunca se vuelve a
  incluir en el HTML tras un error ni se guarda en el navegador por JavaScript.
- Mensaje genérico para credenciales incorrectas, cuentas inexistentes o inactivas.
- CSRF y renovación de sesión/token al autenticar, conservando el flujo de Django.
- Redirecciones posteriores limitadas al mismo sitio.
- La pantalla pública de acceso no carga JavaScript de terceros y aplica CSP.
- Cookies de sesión HttpOnly y SameSite=Lax, cierre al terminar la sesión del
  navegador y caducidad configurada de ocho horas. No es un temporizador de inactividad.

## Límite compartido de intentos

El backend protege tanto `/` como `/admin/login/` utilizando Redis y operaciones
atómicas, también cuando existen varios procesos de Gunicorn. La ventana es de
15 minutos, con límites de 5 intentos fallidos por pareja usuario/IP,
10 por usuario entre distintas IP y 50 por IP entre distintos usuarios.
Las reservas en curso también cuentan para impedir evasiones concurrentes.
Una autenticación correcta limpia los contadores de ese usuario/pareja y no
consume cuota de fallos por IP. El bloqueo es temporal; no cambia `is_active`
ni la contraseña en PostgreSQL.

Redis guarda claves HMAC de los identificadores y contadores con caducidad,
no usuarios o contraseñas en texto claro. En Compose tiene volumen persistente,
puerto sin publicar y política sin expulsión de claves. Si Redis falla, el login
no continúa sin protección: el acceso público devuelve 503. Las sesiones ya
iniciadas no necesitan Redis para consultar la app.

La aplicación toma la IP de `REMOTE_ADDR`. Solo utiliza `X-Forwarded-For` si el
peer pertenece a las redes configuradas explícitamente en `IVEM_TRUSTED_PROXIES`.
Verificar antes que Nginx escribe una cadena fiable y que no se puede acceder
públicamente al upstream. No confiar en cabeceras enviadas directamente por el cliente.
Con una red compartida/NAT, varios usuarios pueden compartir la cuota por IP.

## Desarrollo en Windows

```powershell
git pull --ff-only origin dev
docker compose up --build -d
```

Compose añade automáticamente `login-cache`. No hay migraciones ni cambios de
usuarios, contraseñas, folios o documentos. Puede ser necesario iniciar sesión
nuevamente porque cambia la clase del backend de autenticación.
No eliminar los volúmenes del proyecto para actualizar.

Pruebas con los servicios disponibles:

```powershell
docker compose exec web python manage.py test
```

Las pruebas de protección usan un prefijo aleatorio y borran exclusivamente sus
propias claves; no vacían Redis ni alteran contadores reales.

## Producción: requisitos antes del despliegue

Esta entrega NO instala servicios ni modifica Nginx en producción.

- Proporcionar un Redis privado compartido por todos los workers y configurar
  `IVEM_LOGIN_REDIS_URL`. Usar autenticación/TLS cuando corresponda, sin exponer
  Redis a Internet. Si no existe el servicio, no se podrá iniciar una sesión nueva.
- Configurar los proxies reales con `IVEM_TRUSTED_PROXIES` (CIDR separados por comas).
  No asumir que la IP del proxy sea la misma que en Docker local.
- Definir `IVEM_SECRET_KEY` mediante un gestor de secretos: clave aleatoria larga,
  no versionada ni compartida por chat. La compatibilidad de desarrollo conserva
  la clave antigua solo cuando no se configura una externa. No utilizar esa
  clave de desarrollo en producción. Cambiarla invalida sesiones, no contraseñas
  ni documentos; no añadir una clave pública antigua como fallback.
- Servir el login mediante HTTPS en Nginx. Activar `IVEM_COOKIE_SECURE=true` solo
  después de verificar HTTPS, y revisar la configuración de proxy de Django.
  No activar cookies Secure en el localhost HTTP de desarrollo.
- El nuevo diseño y el icono de candado no implican que HTTP esté cifrado.
