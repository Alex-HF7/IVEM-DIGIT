# Apariencia e identidad

El módulo se encuentra en **Menú de usuario → Apariencia e identidad**, dentro
de la interfaz de la aplicación (`/apariencia/`). También sigue disponible desde
Django Admin. El menú solo aparece con permisos; la URL y las solicitudes POST
comprueban los mismos permisos en el servidor.

## Página web

Abrir la pestaña **Página web**.

- Cambiar color institucional, botones, fondo, texto y color secundario.
- Reemplazar logotipos de navegación y acceso, icono y pie de página.
- Usar **Vista previa sin guardar**: valida los datos y abre otra pestaña; no
  cambia la configuración ni publica imágenes. Volver al formulario para guardar.
- **Restaurar los valores e imágenes originales** recupera los valores del
  proyecto, sin borrar los archivos guardados ni tocar las imágenes de impresión.

Se comprueba contraste de texto de al menos 4.5:1 sobre el fondo y tarjetas,
y de al menos 3:1 para los colores principales sobre blanco. Los colores de
texto de botones y navegación se eligen automáticamente para conservar contraste.
La paleta se aplica también al acceso y a las gráficas. El PDF no carga esta paleta.
Las páginas de error conservan un estilo de respaldo si la base no está disponible.

## Formato imprimible, por año

Abrir la pestaña **Formato imprimible**, seleccionar un año existente y pulsar
**Consultar año**. Subir únicamente las imágenes izquierda y derecha.

La vista previa muestra las imágenes y el formato completo con datos ficticios,
sin iniciar la impresión. **No se pueden editar colores, papel, márgenes,
fuentes, columnas, sello, espaciado ni posiciones del formato.**

El oficio y su acuse utilizan las mismas dos imágenes. Se conserva exactamente
el CSS original: papel carta vertical, margen de impresión de 1 cm y logos con
40 px de alto y 120 px de ancho máximo. Las dimensiones del archivo nuevo deben
coincidir con las originales para mantener la proporción y el espacio ocupado.

Cada año tiene su propio perfil. Cambiar las imágenes de un año no modifica las
de otros. Los años sin perfil usan las imágenes originales. Cambiar un perfil
afecta las impresiones futuras de ese año; no modifica registros ni PDF adjuntos
ya subidos. No hay un archivo histórico de cada impresión generada por el navegador.
El año del perfil existente no se puede renombrar.

## Medidas y formatos

| Uso | Dimensiones originales |
| --- | --- |
| Logo de navegación | 1985 × 617 px |
| Logo del acceso | 1985 × 617 px |
| Icono de la página | 64 × 64 |
| Pie de página web | viewBox 300 × 16 |
| Logo izquierdo del formato | 477 × 149 px |
| Logo derecho del formato | viewBox 986.18 × 364.74 |

**Se recomienda SVG**, con un lienzo/viewBox de esas medidas y textos convertidos
a curvas cuando sea posible. Se aceptan PNG/JPEG del mismo tamaño; los valores
fraccionarios se redondean al píxel más cercano (logo derecho: 986 × 365).
No se redimensionan ni deforman los archivos silenciosamente.

Máximo **5 MB por imagen**. Se rechazan imágenes animadas, rotación EXIF sin
aplicar, SVG con scripts, entidades, instrucciones XML, hojas de estilo globales,
enlaces o recursos externos. Usar un SVG simple con atributos de presentación.
Las imágenes nuevas se sirven con tipo de contenido fijo, `nosniff` y sandbox.
La configuración no permite introducir HTML, JavaScript o CSS libre.

## Permisos y conservación

El encargado necesita los permisos específicos, asignados a su usuario o grupo:

- `apariencia.change_webappearance`: configurar la página web.
- `apariencia.add_printidentity`: crear un perfil para un año sin configurar.
- `apariencia.change_printidentity`: modificar o restaurar perfiles existentes.

No se necesita `is_staff` para la interfaz de la aplicación. El acceso mediante
Django Admin exige además el permiso de Acceso técnico Django y los permisos
de los modelos correspondientes. Los superusuarios tienen acceso completo.
La vista previa también exige permiso para guardar el perfil correspondiente.
Los permisos de
oficios y la configuración de tablas anuales continúan separados.

Se registra quién guardó el último cambio y cuándo, además del historial nativo
del administrador. Las imágenes guardadas tienen nombre único y son inmutables.
Al reemplazarlas o restaurar originales se conservan las versiones anteriores
para no romper referencias. Tener esto en cuenta al planificar almacenamiento.
Las imágenes de identidad son públicas para que el logo se muestre antes del
login; los PDF de oficios mantienen su acceso protegido.

## Migraciones y despliegue

Esta entrega añade exclusivamente tres tablas de configuración e imágenes:
`apariencia_brandimage`, `apariencia_webappearance` y `apariencia_printidentity`,
y sus permisos. Inicializa la web con los colores originales y sin reemplazos
de imágenes. **No altera las tablas anuales, registros, folios ni secuencias.**

En desarrollo con Docker:

```powershell
git pull --ff-only origin dev
docker compose up --build -d
```

Compose aplica las migraciones nuevas al arrancar. Recargar con Ctrl+F5 y abrir
el administrador. Las imágenes se guardan en `MEDIA_ROOT/identidad`, dentro del
volumen de archivos adjuntos existente.

Antes de producción, respaldar PostgreSQL y MEDIA_ROOT y probar en una copia.
Instalar requirements.txt, aplicar `python manage.py migrate apariencia` y
reiniciar el servicio según el procedimiento del servidor. Las rutas de
`/apariencia/` deben llegar a Django; no necesitan un alias público de MEDIA_ROOT.
El límite de subida de Nginx debe permitir la solicitud completa cuando se
cargan varias imágenes. No ejecutar SQL manual ni borrar volúmenes o tablas
para instalar este módulo.
