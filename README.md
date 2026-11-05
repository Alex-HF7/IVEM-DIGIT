<p align="center">
  <img src="plantilla/static/plantilla/img/logo.png" alt="Logo del Proyecto" width="200"/>
</p>

# Aplicacion Web para la Digitalizacion Documental

Este es un proyecto desarrollado con Django para **gestionar los oficios que ingresan al instituo de diferentes dependencias**.

## Instalación

1. Clona el repositorio:
    ```bash
    git clone https://github.com/Alex-HF7/IVEM-DIGIT.git
    ```

2. Crea y activa un entorno virtual:
    ```bash
    python -m venv env
    source env/bin/activate  # Linux/Mac
    .\env\Scripts\activate   # Windows
    ```

3. Instala las dependencias:
    ```bash
    pip install -r requirements.txt
    ```

4. Configura la base de datos en el archivo `settings.py` o mediante el archivo `.env` (variables de entorno).

5. Realiza las migraciones:
    ```bash
    python manage.py makemigrations
    python manage.py migrate
    ```

6. Crea un superusuario para acceder al panel de administración:
    ```bash
    python manage.py createsuperuser
    ```

7. Ejecuta el servidor de desarrollo:
    ```bash
    python manage.py runserver
    ```

## Uso

- Accede a la aplicación en tu navegador: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)  
- Accede al panel de administración: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

## Estructura del Proyecto

| Carpeta / Archivo   | Descripción                                    |
|----------------------|------------------------------------------------|
| /app/                | Aplicaciones principales                       |
| /templates/          | Plantillas HTML                                |
| /static/             | Archivos estáticos (CSS, JS, imágenes)         |
| /media/              | Archivos cargados por usuarios                 |
| manage.py            | Comando principal de Django                    |
| requirements.txt     | Archivo de dependencias                        |


### Reiniciar el sistema tras crear tablas dinámicas

Cuando se crean nuevas tablas dinámicas cada año (por ejemplo, `oficios_ucg_2025`), es **necesario reiniciar el servidor** para que Django detecte y cargue las nuevas tablas. Para reiniciar el servicio Gunicorn:

```bash
sudo systemctl restart nombre_del_proyecto
```

## Autor

- **Nombre**: Ing. Alexander Hueramo Fulgencio
- **Email**: hf.alex00@gmail.com

## Desarrollo local en Windows con Docker Desktop

Abre Docker Desktop y espera a que el motor esté activo. Usa PowerShell desde
una carpeta de proyectos, por ejemplo `$HOME\Documents`, no desde System32.
Requiere Git para Windows.

```powershell
cd "$HOME\Documents"
git clone --branch dev https://github.com/Alex-HF7/IVEM-DIGIT.git
cd IVEM-DIGIT
docker compose up --build -d
docker compose logs -f web
```

Cuando aparezca `Starting development server`, abre **http://localhost:8000/**
en el navegador de tu computadora. Ctrl+C cierra la vista de registros y deja
los contenedores activos. Crea tu propia cuenta local:

```powershell
docker compose exec web python manage.py createsuperuser
```

Inicia sesión con esa cuenta. El arranque aplica las migraciones y prepara los
grupos UCG y Delegacion y las tablas del año actual. No incluye datos ni cuentas
de producción. Las credenciales anteriores del entorno en la nube no se copian.
La contraseña de PostgreSQL en Compose es exclusiva para esta base local y el
puerto de la base no se publica. Este archivo no es una configuración de producción.

Comandos útiles:

```powershell
# Detener conservando la base y los archivos adjuntos
docker compose down
# Volver a iniciar
docker compose up -d
# Actualizar código y reconstruir
git pull --ff-only origin dev
docker compose up --build -d
# Ejecutar las pruebas
docker compose exec web python manage.py test
```

Los datos se conservan en volúmenes de Docker. `docker compose down -v` los
elimina. Si el puerto 8000 está ocupado, ejecuta `$env:IVEM_PORT="8001"` antes
de iniciar y accede por http://localhost:8001/. Para una conexión fallida,
consulta `docker compose ps` y `docker compose logs web db`.
