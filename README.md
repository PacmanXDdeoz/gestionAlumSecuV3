# Sistema de Gestión Escolar

Aplicación Flask para la gestión de alumnos, docentes, materias y calificaciones.

## Descarga e instalación del proyecto

### Variables de entorno

Copia `.env.example` a `.env` y completa los valores reales (secretos: nunca
subas `.env` al repositorio). La aplicación también acepta `db_uri.secret`
(compatibilidad) con la URI de PostgreSQL.

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

---

## Base de datos (Fase 2)

### Entornos

| Config | Base de datos | Uso |
|---|---|---|
| `config.local` | Remota AlwaysData (`DATABASE_URI` en `.env` o `db_uri.secret`) | **Principal** (producción/desarrollo) |
| `config.testing` | Local (`DATABASE_URI_LOCAL`) | Backup / entorno secundario / tests |

La URI de la base local de respaldo se define en `.env` como `DATABASE_URI_LOCAL`.
La aplicación principal siempre usa la remota.

### Migraciones (cadena unificada)

El historial quedó unificado en **2 migraciones** (las 8 antiguas están
archivadas en `migrations/versions_archive/` como referencia, fuera del alcance
de alembic):

| Revisión | Contenido |
|---|---|
| `0001_initial` | Esquema `alejandra` + 12 tablas + seeds de roles (1=admin, 2=docente) y 13 materias (`ON CONFLICT DO NOTHING`, idempotente) |
| `0002_rol_fk` | `docentes.rol` VARCHAR → INTEGER con FK al catálogo `alejandra.rol` y conversión de datos (`'admin'→1`, `'docente'→2`) |
| `0003_horarios_grupo` | Añade `horarios.grupo_id` (FK a `grupos`): cada clase del horario queda ligada al grupo donde se imparte. Permite que el docente vea **solo** los alumnos de sus grupos (filtro del roster por horario) |
| `0004_alumno_tutor` | Añade `alumnos.tutor_id` (FK a `docentes`): profesor/tutor asignado al alumno (opcional), editable desde la vista de edición del docente |
| `0005_nota_texto` | Añade `calificaciones_materia.nota_texto`: nota/comentario que el docente comparte con el alumno **por materia** (la que muestra la boleta 💬 y el panel) |

**BD nueva** (solo ejecuta el upgrade):

    flask db upgrade

**BD existente** migrada desde la cadena antigua (con backup previo, ver más
abajo):

    flask db stamp --purge 0001_initial
    flask db upgrade

Verificación:

    flask db history
    flask db current

> ⚠️ **Siempre haz un backup antes de `stamp --purge` o `upgrade` sobre una BD
> con datos** (comando en la sección Backup).

### Datos de prueba: `flask seed`

Puebla la BD con grupos (con currículum), docentes de prueba (**todos con
rol = 2**) y alumnos con código de acceso único.

    # Por defecto: 5 docentes (rol=2) y 18 alumnos
    flask seed

    # Personalizado: 5 docentes, 12 alumnos, contraseña conocida
    flask seed --docentes 5 --alumnos 12 --password Docente123

    # Fuerza la creación de alumnos aunque la BD ya tenga datos
    flask seed --force

Opciones:

- `--docentes N` — número de docentes de prueba (rol = 2, por defecto 5).
- `--alumnos N` — número de alumnos de prueba (por defecto 18).
- `--password` — contraseña común de los docentes de prueba (por defecto `Docente123`).
- `--force` — añade alumnos aunque la BD ya tenga registros.

Credenciales generadas: `docente1@escuela.test … docenteN@escuela.test / <password>`.

### Códigos QR: escaneo nativo, dominio, carpeta y sweep de huérfanos

Los códigos QR de la credencial de cada alumno codifican la **URL absoluta**
de su boleta pública (`https://midominio.com/buscar/<id_alumno>`) en lugar del
ID crudo o del código de acceso. Al escanear la credencial con la cámara
nativa del celular se abre directamente la vista del alumno (sin librerías JS
de escaneo en `/buscar/`).

#### ¿Dónde cambiar el dominio que se guarda en los QRs?

Se configura en **una sola variable** del archivo `.env`:

    PUBLIC_BASE_URL=http://192.168.100.8:5000

- **Definida** → se usa **siempre** (dentro y fuera de requests): los QRs se
  guardan con `http://192.168.100.8:5000/buscar/<id>`. Es la opción
  recomendada para testeo con el celular en la red local.
- **Vacía** → se usa el host de la petición (útil en producción detrás de un
  dominio real).
- **Guard anti-placeholder**: si el valor contiene `<` (p. ej. el template
  `https://<tu-app>.onrender.com` copiado a Render sin editar), se trata
  como vacía: el QR usa el host real de la petición y nunca codifica un
  placeholder.

> ⚠️ En testeo local el servidor debe escuchar en esa dirección para que el
> celular pueda abrir la URL del QR:
> `flask run --host=0.0.0.0 --port=5000`

##### Cambiar de dominio (deploy temporal → dominio real)

El QR guarda la URL **absoluta en el momento de generarse**; la BD solo guarda
la ruta relativa del PNG (`qrcodes/alumno_<id>.png`), no la URL. Por eso
cambiar de dominio **no toca la BD**, solo hay que **regenerar los PNGs**:

1. Cambia `PUBLIC_BASE_URL` en el entorno (p. ej. Render: del dominio
temporal `https://xxx.onrender.com` al dominio real `https://midominio.com`).
2. Ejecuta una vez: `flask regenerate-qrs`.
3. Listo: los QRs de los alumnos existentes se reescriben con el nuevo
dominio (mismo nombre de archivo, se sobreescriben); los alumnos nuevos ya
usan el dominio configurado automáticamente.

La ruta `/qr/<archivo>` sirve con `Cache-Control: no-cache` (revalidación
ETag/304), así los navegadores no muestran el QR viejo en caché tras la
regeneración. Con disco persistente (`QR_CODES_FOLDER`) los PNGs se
reescriben en el disco.

#### ¿Dónde se guardan los archivos QR?

Por defecto los PNGs se escriben en `app/static/qrcodes/`; la columna
`alumnos.codigo_qr` guarda la ruta relativa (`qrcodes/alumno_<id>.png`) y las
plantillas los sirven por la ruta pública `/qr/<archivo>` (que resuelve la
carpeta con la misma lógica de escritura).

Para **persistirlos fuera del código** (p. ej. en un disco persistente de
Render, cuyo filesystem se borra en cada deploy) define en `.env`:

    QR_CODES_FOLDER=/ruta/absoluta/a/qrcodes

Cuando `QR_CODES_FOLDER` está definida, la app escribe **y sirve** los PNGs
desde esa carpeta (ruta `/qr/…`), así los QRs sobreviven a los deploys y
reinicios de instancia. Después del primer deploy, ejecuta
`flask regenerate-qrs` para volver a escribir los QRs de los alumnos
existentes en la carpeta persistente.

#### Regeneración y sweep de QRs huérfanos

Los alumnos **ya registrados** conservan su QR antiguo (ID/código) hasta que se
regeneren. Un solo comando hace ambas tareas:

    flask regenerate-qrs

> 💡 **Sin acceso a la Shell de Render (plan Free)?** También puedes
> regenerarlos desde la interfaz: `/admin/` → **Mantenimiento → Regenerar
> QRs**. La acción corre en el servidor, reescribe los PNGs con el dominio
> actual y barre los huérfanos, sin necesidad de comandos.

1. **Regenera** los QRs de todos los alumnos existentes con el formato/dominio
   actual (requiere `PUBLIC_BASE_URL` en `.env` o ejecutarse dentro de un
   request).
2. **Sweep de huérfanos**: elimina los PNGs de alumnos que **ya no existen en
   la BD** (p. ej. tras una limpieza de la tabla `alumnos`), de modo que la
   carpeta refleja siempre el estado real y nunca muestra QRs de alumnos
   eliminados.

Salida de ejemplo:

    ✓ QRs regenerados para 2 alumno(s).
    🗑  Eliminados 1 QR(s) huérfano(s) de alumnos ya eliminados.

Casos particulares:

- **Sin alumnos en la BD** → el sweep igual se ejecuta y limpia todos los PNGs.
- **Carpeta de QRs inexistente** → avisa y termina sin error.
- El sweep **solo toca archivos** `alumno_<id>.png` (regex estricta de
  dígitos): ningún otro archivo de la carpeta se ve afectado.

#### Los tests nunca escriben en la carpeta real

La suite de tests **no ensucia `app/static/qrcodes/`**: el entorno
`config.testing` redirige `QR_CODES_FOLDER` a un directorio temporal en `/tmp`
(`gestalumn_test_qrcodes_*`), creado automáticamente al importar la config.
Así los QRs de los alumnos de prueba (IDs bajos) no aparecen como si fueran de
alumnos reales ya eliminados de la BD.

### Docentes ven solo a sus grupos (horarios)

El admin asigna los grupos en **Gestionar Horarios** (`/admin/horarios/`): cada
entrada liga docente + materia + grupo. Con eso, el roster de una materia solo
muestra a los alumnos de los grupos donde el docente imparte esa materia según
su horario; sin horario asignado, el roster queda vacío (regla estricta).

### Contraseña del admin: `flask reset-password`

Busca al docente administrador y le asigna una contraseña conocida
(usa `generate_password_hash`):

    # Por defecto: admin@example.com / Admin2026!
    flask reset-password

    # Personalizado
    flask reset-password --email admin@example.com --password 'MiClaveSegura!'

Opciones:

- `--email` — email del docente administrador (por defecto `admin@example.com`).
- `--password` — nueva contraseña (por defecto `Admin2026!`).

Si no encuentra el email, busca por nombre parecido a "admin".

### Backup / restore: `scripts/backup_db.py`

Genera un archivo SQL con `CREATE TABLE` + `INSERT` de todas las tablas de los
esquemas `alejandra` y `public` (incluida `alembic_version`), sin depender de
`pg_dump`. Los archivos quedan en `backups/` (gitignored).

    # Backup de la BD principal (usa DATABASE_URI de .env o db_uri.secret)
    python scripts/backup_db.py

    # Backup de una BD concreta (por ejemplo, la local de respaldo)
    python scripts/backup_db.py "postgresql://usuario:clave@localhost:5432/mi_bd"

    # Archivo de salida explícito
    python scripts/backup_db.py <URI> -o backups/mi_backup.sql

Restauración manual (los archivos son SQL plano):

    psql -U usuario -d nombre_bd -f backups/<archivo>.sql

### Acceso a la BD

Para obtener la estructura de la BD ejecuta:

    flask db upgrade
    flask db history

> ⚠️ **Si tu contraseña de PostgreSQL contiene `#`** (p. ej. `uFD#...`), el
> valor de `DATABASE_URI` en `.env` debe ir **entre comillas dobles**
> (`DATABASE_URI="postgresql://..."`), porque si no, la carga del `.env` la
> corta en el `#` (lo interpreta como comentario) y la URI queda rota.
>
> También evita tener una `DATABASE_URI` **antigua exportada en tu shell**:
> `load_dotenv` no sobreescribe variables existentes, así que al reiniciar el
> servidor desde ese shell se usaría la URI vieja/truncada. Si te falla la
> conexión al arrancar, ejecuta primero:
>
>     unset DATABASE_URI
>     flask run

---

## Seguridad (cabeceras HTTP y CSP)

Toda respuesta de la aplicación incluye cabeceras de seguridad HTTP,
añadidas en la factory (`app/__init__.py`, `register_security_headers`):

| Cabecera | Valor | Propósito |
|---|---|---|
| `X-Frame-Options` | `DENY` | Anti-clickjacking (la app no puede incrustarse en iframes) |
| `X-Content-Type-Options` | `nosniff` | Evita que el navegador adivine el MIME de respuestas no HTML |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | No filtra la URL completa al salir a otros orígenes |
| `Content-Security-Policy` | ver abajo | Restringe scripts, estilos y conexiones a orígenes permitidos |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | **Solo sobre HTTPS** (HSTS); no se envía en la LAN de pruebas HTTP |

### Content-Security-Policy (CSP laxo)

La política es **deliberadamente laxa** porque el diseño actual depende de
**Tailwind CDN** (`https://cdn.tailwindcss.com`) y de estilos/scripts inline:

    default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'

- `object-src 'none'` y `frame-ancestors 'none'` bloquean plugins y la
  incrustación de la app (refuerza el `X-Frame-Options`).
- `connect-src 'self'` solo permite llamadas AJAX/fetch al propio dominio
  (los `fetch()` de las APIs `/api/*`).
- `'unsafe-inline'` y el dominio del CDN son **necesarios hoy** por Tailwind
  CDN y los bloques `<style>`/`<script>` de las plantillas.

### Endurecer en producción (recomendado a futuro)

Si algún día los estilos/scripts pasan a un bundle propio (sin CDN ni inline),
se puede endurecer el CSP quitando `'unsafe-inline'` y el dominio del CDN, y
habilitando HSTS de forma permanente (el servidor de AlwaysData ya sirve HTTPS).
El punto exacto está comentado en el código de `register_security_headers`.

### Verificar las cabeceras

    curl -sI https://midominio.com/ | grep -iE 'x-frame|x-content|referrer|content-security'

La suite de tests (`test_app_factory.py`) fija una regresión: toda respuesta
(200 y 404) lleva las cabeceras, el CSP incluye `object-src 'none'` y
`frame-ancestors 'none'`, y el HSTS **no** aparece sobre HTTP.

---

## Despliegue en Render (Web Service)

Configuración probada para desplegar este proyecto en [Render](https://render.com)
apuntando a tu PostgreSQL remoto (AlwaysData).

### Build command (limpio)

`gunicorn` ya está en `requirements.txt`, así que el build solo instala
dependencias y aplica las migraciones:

    pip install -r requirements.txt && flask db upgrade

### Start command

    gunicorn --bind 0.0.0.0:$PORT entrypoint:app

### Runtime

- **Runtime**: Python 3 fijado por `runtime.txt` en la raíz
  (`python-3.12.3`): Render usa 3.12, la misma versión del proyecto y donde
  están validadas las dependencias pinneadas (no usar el Python 3.14 por
  defecto de Render: `psycopg2-binary` y `Pillow` no tienen wheels para él).
- **Plan**: Free (se duerme a los 15 min de inactividad; la primera petición
  tarda ~50 s en "despertar") o Starter para uso continuo.

### Variables de entorno

| Variable | Valor | Obligatoria |
|---|---|---|
| `APP_SETTINGS_MODULE` | `config.prod` | Sí |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` | Sí |
| `DATABASE_URI` | `postgresql://usuario:clave@host-alwaysdata:5432/nombre_bd` | Sí |
| `ADMIN_EMAILS` | `admin@example.com` | Recomendada |
| `PUBLIC_BASE_URL` | `https://<tu-app>.onrender.com` | **Sí** (los QRs se guardan con este dominio) |
| `FLASK_APP` | `entrypoint` | Sí (necesaria para `flask db upgrade` del build) |
| `MAIL_*` | opcionales | No |

**Secret Files**: no hacen falta — todas las credenciales van como variables
de entorno (la app lee `SECRET_KEY`/`DATABASE_URI` del entorno).

> 💡 El proyecto incluye un `.env.prod` local (gitignored) **generado con una
> `SECRET_KEY` aleatoria y tu `DATABASE_URI` real de AlwaysData**, listo para
> copiar sus líneas en las Environment Variables de Render. Solo tienes que
> cambiar `PUBLIC_BASE_URL` por la URL real de tu servicio y, si usas disco,
> descomentar `QR_CODES_FOLDER`.

### QRs en disco persistente

El filesystem de Render es **efímero** (se borra en cada deploy). Para no
perder los QRs generados en runtime:

1. Crea un **Disco** en el servicio y móntalo en `/var/data`.
2. Añade la variable `QR_CODES_FOLDER=/var/data/qrcodes`.
3. Tras el primer deploy, ejecuta una vez (shell de Render o local contra la
   BD remota): `flask regenerate-qrs`.

Con esto la app escribe **y sirve** los QRs desde el disco (ruta pública
`/qr/<archivo>`) y sobreviven a los deploys. Sin disco, habría que regenerarlos
tras cada deploy.

### Antes del primer deploy

- En AlwaysData: habilita el **acceso remoto** a PostgreSQL y permite los
  **IPs de salida (egress) de Render** de tu región (si hay firewall).
- Verificación post-deploy:
  `curl -sI https://<tu-app>.onrender.com/` debe mostrar las cabeceras de
  seguridad (`content-security-policy`, `x-frame-options`).
