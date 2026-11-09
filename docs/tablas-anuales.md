# Operación automática de tablas anuales

El personal utiliza **Menú de usuario → Carpetas anuales**, con el perfil
Gestión de carpetas. La pantalla técnica de Configuración de tablas sigue
disponible solo para responsables autorizados.
No necesita SQL, comandos de migración ni reiniciar el servicio para abrir un año nuevo.

## Crear un año

1. Añadir una configuración indicando el año de cuatro dígitos y, opcionalmente,
   una descripción.
2. Guardar. El sistema crea las tablas de UCG y Delegación con sus secuencias,
   funciones y triggers dentro de la misma transacción que la configuración.
3. Si falla alguna parte, no se guarda una configuración parcial. La pantalla
   muestra el error y permite volver a intentarlo; los detalles quedan en el registro técnico.
4. El año aparece en el menú Registro y sus tablas se pueden consultar también
   en el administrador sin reiniciar el servicio.

El año no se puede renombrar después de guardarlo. Para otro año, crear otra
configuración. No se permite borrar configuraciones desde el administrador.
La descripción sí se puede modificar.

## Comprobar un año existente

Seleccionar su configuración y ejecutar la acción **Comprobar y completar las
tablas de los años seleccionados**. Puede repetirse: conserva registros, referencias
a PDF, folios y el avance de las secuencias existentes. Completa objetos faltantes.
Si falta una secuencia, la nueva comienza después del folio máximo de su tabla.

No se reinicia una secuencia existente. Si está desalineada, un trigger está
desactivado o la estructura de una tabla es incompatible, se informa del fallo
y no se aplican cambios a ese año. Un administrador técnico debe revisar esos
casos sobre una copia de los datos antes de corregirlos. Otros años seleccionados
se comprueban de forma independiente.

## Consultar los oficios

El administrador muestra los campos reales de las tablas anuales en modo consulta.
Las altas, ediciones y asignaciones de folio continúan en las pantallas de la app,
respetando sus permisos y estados. Las tablas existentes conservan sus nombres.

Los modelos de consulta usan un registro separado y `managed=False`: Django no
propone crear esas tablas mediante `makemigrations`. La creación automática sigue
siendo responsabilidad de Configuración de tablas.

## Entrega y producción

No hay una migración nueva ni una conversión de datos históricos en esta entrega.
No se añaden restricciones ni índices a las tablas existentes. El flujo automático
mantiene el esquema de creación anterior; la obligatoriedad de fechas se valida
actualmente en el backend.

Antes de actualizar producción, probar sobre una copia respaldada de PostgreSQL
y archivos adjuntos, incluyendo la acción de comprobación de años existentes.
El proceso que crea años debe conservar permisos para crear tablas, secuencias,
funciones y triggers en el esquema `public`; no requiere ser superusuario.
Las operaciones de creación/comprobación quedan serializadas por año en PostgreSQL.
