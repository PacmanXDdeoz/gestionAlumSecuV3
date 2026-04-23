## Descarga e instalación del proyecto

### Variables de entorno

#### Linux/Mac

    export FLASK_APP="entrypoint"
    export FLASK_ENV="development"
    export APP_SETTINGS_MODULE="config.local"

#### Windows

    set "FLASK_APP=entrypoint"
    set "FLASK_ENV=development"
    set "APP_SETTINGS_MODULE=config.local"

### Instalación de dependencias

    pip install -r requirements.txt

## Ejecución con el servidor que trae Flask

    flask run

### Acceso a la BD

Para obtener la estructura de la BD ejecuta:

    # flask db migrate
    flask db upgrade
    flask db history