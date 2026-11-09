# Usuarios, carpetas y acceso técnico

## Uso diario sin Django Admin

Desde el menú de usuario:

- **Gestión de usuarios** permite crear cuentas y consultar un listado paginado.
  Se valida nombre único, contraseña y confirmación. No muestra contraseñas ni
  permite borrar cuentas, cambiar superusuarios o editar permisos individuales.
- **Carpetas anuales** permite indicar año y descripción. El sistema crea las
  tablas/carpetas de UCG y Delegación automáticamente, con folios independientes.
  No permite borrar carpetas ni renombrar años históricos. El año creado aparece
  en Registro para los usuarios con acceso al departamento correspondiente.
- **Administración técnica** solo aparece para responsables técnicos autorizados.

Los menús se ocultan sin permiso y los servidores comprueban los mismos permisos
en cada GET/POST. Ocultar botones no sustituye las comprobaciones de autorización.
Las altas usan CSRF, transacciones, validación y registro de auditoría de Django.
Los mensajes de éxito aparecen en la notificación habitual de la aplicación.

## Perfiles

| Grupo | Facultades |
| --- | --- |
| UCG | Registro, edición de pendientes, consulta y archivos de UCG |
| Delegacion | Lo mismo para Delegación |
| Administración de oficios | Ambos departamentos, pendientes, asignación de folios y eliminación lógica |
| Gestión de usuarios | Consultar cuentas y crear operadores departamentales |
| Gestión de carpetas | Consultar y crear carpetas anuales |
| Acceso técnico Django | Entrar a Django Admin, además de necesitar `is_staff`; los permisos de sus módulos se asignan por separado |

Un usuario puede combinar perfiles. **Ningún perfil crea superusuarios**.
El superusuario conserva el acceso de recuperación y puede crear cuentas con
perfiles operativos desde la nueva pantalla. Si selecciona Acceso técnico Django,
la cuenta nueva se marca `is_staff`, pero no se hace superusuario ni recibe
permisos generales de modelos. Dar solo ese perfil no permite leer oficios,
gestionar otras cuentas ni editar configuraciones del administrador.

Un gestor de usuarios que no sea superusuario solo puede asignar UCG/Delegacion,
y únicamente si esos grupos no tienen permisos adicionales. No puede delegar
los perfiles de gestión ni el técnico, aunque manipule campos o identificadores
al enviar el formulario. El responsable técnico puede asignar esos perfiles a
cuentas existentes desde Django Admin. La primera asignación de perfiles se hace
con un superusuario, sin SQL manual.

Los permisos de apariencia siguen siendo los existentes e independientes de los
perfiles documentales. No se concede apariencia automáticamente por ser staff.

## Configuración inicial recomendada

1. Acceder con el superusuario de recuperación existente.
2. Abrir **Gestión de usuarios** desde el menú de la aplicación.
3. Crear las cuentas de trabajo y marcar solo los perfiles necesarios. Para un
   administrador operativo pueden combinarse Administración de oficios, Gestión
   de usuarios y Gestión de carpetas, sin marcar Acceso técnico Django.
4. Usar esas cuentas para el trabajo diario. Reservar el superusuario para tareas
   técnicas y recuperación, no compartirlo entre el personal.
5. Para una cuenta técnica existente, asignar el grupo Acceso técnico Django y
   habilitar `is_staff`, además de los permisos específicos de los modelos que
   deba administrar. No asignar `is_superuser` por comodidad.

El listado de cuentas no ofrece cambios de contraseña ni edición de cuentas.
La recuperación de contraseña y cambios de permisos de cuentas existentes siguen
siendo responsabilidad técnica. Estas restricciones evitan ampliar el alcance
de las altas operativas a acciones sensibles sobre otras cuentas.

## Permisos exactos

Todos los permisos personalizados pertenecen a ConfiguracionTable como soporte
estable; no se añaden tablas de oficios ni columnas para gestionarlos.

- `gestion_tables.view_all_documents`: acceso a ambos departamentos sin depender
  de los grupos departamentales.
- `gestion_tables.view_pending_documents`: abrir el listado de pendientes.
- `gestion_tables.assign_folio`: asignar folio, respetando acceso al departamento.
- `gestion_tables.delete_document`: eliminación lógica, respetando departamento.
- `gestion_tables.access_technical_admin`: puerta de acceso al administrador
  técnico; para cuentas no superusuario también exige `is_staff`.
- `auth.add_user` / `auth.view_user`: alta y consulta de cuentas en la pantalla nueva.
- `gestion_tables.add_configuraciontable` / `view_configuraciontable`: creación y
  consulta de carpetas en la pantalla nueva.

Los permisos de consulta no conceden alta. `is_staff` solo deja de ser una llave
para todos los oficios: por sí solo tampoco permite entrar a Django Admin.
La consulta técnica de tablas anuales exige también view_all_documents.

## Migración y conservación

La migración `gestion_tables.0002_operational_roles` añade metadatos de permisos,
grupos y relaciones de autorización. **No cambia el esquema de las tablas anuales,
registros, PDF, contraseñas, flags de usuario, folios ni secuencias**.

Los `staff` no superusuario existentes se incorporan a Administración de oficios
para conservar sus facultades documentales anteriores. No reciben por ello altas
de usuarios, creación de carpetas ni acceso técnico. Conservan cualquier permiso
que ya tuvieran explícitamente, pero necesitan el nuevo permiso técnico para
usar Django Admin. Los superusuarios activos conservan el acceso técnico.

Si existen cuentas staff pero no un superusuario activo con `is_staff`, la
migración se detiene antes de restringir accesos. El responsable técnico debe
crear o habilitar uno de recuperación. Si es una instalación nueva sin cuentas,
se puede migrar y ejecutar `createsuperuser` después, como antes.

Los nombres de perfiles tienen permisos definidos. Si ya existe un grupo con
uno de esos nombres y facultades adicionales, o con miembros a los que se
concederían facultades nuevas, la migración se detiene para revisión técnica.
No elimina grupos ni reemplaza permisos silenciosamente.

## Actualización de desarrollo

```powershell
git pull --ff-only origin dev
docker compose up --build -d
```

Compose aplica la migración. Iniciar sesión con el superusuario para hacer la
asignación inicial de perfiles. Si el servicio se detiene por los controles de
recuperación o grupos previos, revisar `docker compose logs --tail 100 web` y
resolverlo con el responsable técnico; no borrar volúmenes, cuentas o carpetas.

Antes de producción, respaldar PostgreSQL y archivos, revisar el superusuario de
recuperación y probar la migración sobre una copia. El acceso del personal staff
a Django Admin cambia deliberadamente; comunicar el nuevo flujo antes de desplegar.
No se desplegó esta entrega en producción.

La migración inversa no elimina permisos/grupos o relaciones creadas, para no
borrar asignaciones operativas realizadas después. Volver a código antiguo puede
restaurar su política amplia de `is_staff`; coordinar cualquier reversión y
revisar los accesos, además de restaurar la versión del código.

## Validación

111 pruebas aprobadas, también dentro de Docker con migraciones desde cero.
Se verificaron CSRF, separación de departamentos, altas y consultas independientes,
contraseñas, manipulación de privilegios, grupos previos y recuperación técnica.
La migración de desarrollo conservó las huellas de oficios, configuración anual,
folios/secuencias, contraseñas y flags de las cuentas existentes.

En Chromium, un gestor sin staff creó un operador y un año desde el menú. El año
apareció en Registro y el acceso del gestor a Django Admin fue rechazado. El
operador creado pudo iniciar sesión y consultar UCG; Delegación respondió 403.
Las pantallas de gestión no produjeron errores JavaScript. Bandit no señaló
incidencias en el código nuevo de operación y configuración del administrador.
