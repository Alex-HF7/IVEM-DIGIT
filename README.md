<p align="center">
  <img src="plantilla/static/plantilla/img/logo.png" alt="Logo del Proyecto" width="200"/>
</p>

# Aplicacion Web para la Digitalizacion Documental

Este es un proyecto desarrollado con Django para **gestionar los oficios que ingresan al instituo de diferentes dependencias**.

## Instalación

1. Clona el repositorio:
    ```bash
    git clone https://github.com/Chawder7/IVEM-DIGIT.git
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

- **Nombre**: [Tu nombre o nombre del equipo]  
- **Email**: [Tu correo electrónico]
