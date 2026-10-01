# Este archivo es la receta para armar la imagen del portal.
#
# Una imagen es un paquete que trae Linux, Python, las librerías y nuestro
# código, todo listo para correr. Docker la construye una vez y después levanta
# el proyecto a partir de ella.
#
# La idea es poder correr el proyecto con un solo comando por comodidad. Es por
# esto que Claude me recomendó armar este entorno: así ninguno tiene que
# instalar Python ni MariaDB a mano en su Windows, y todos corremos la misma
# versión de todo. También nos sirve como ambiente de pruebas para la entrega,
# ya que el servidor que iba a pasar el cliente nunca llegó.
#
# Referencia por si quieren profundizar:
# https://docs.docker.com/reference/dockerfile/

# Usamos Python 3.12 porque es la que usa el pipeline y la que pide el
# Makefile. La variante "slim" trae lo mínimo de Linux y pesa bastante menos.
FROM python:3.12-slim

# Para que Python no vaya dejando archivos .pyc, que adentro del contenedor no
# le sirven a nadie.
ENV PYTHONDONTWRITEBYTECODE=1

# Para ver los logs al instante. Sin esto salen con retraso y se hace molesto
# revisar qué pasó.
ENV PYTHONUNBUFFERED=1

# Carpeta donde vive el proyecto adentro del contenedor. Todo lo que viene
# después corre parado acá.
WORKDIR /app

# Django necesita un driver para hablar con MariaDB y ese driver es
# mysqlclient. Como no viene precompilado, se compila al momento de instalarlo,
# y para eso hacen falta un compilador de C y las cabeceras de MariaDB. Son los
# mismos paquetes que instala el pipeline.
#
# El rm del final va pegado en la misma instrucción para que los archivos que
# descarga apt no queden pesando adentro de la imagen.
RUN apt-get update && apt-get install -y --no-install-recommends \
        default-libmysqlclient-dev \
        build-essential \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copiamos primero las dependencias y recién después el código, para aprovechar
# la caché de Docker. El código lo cambiamos todos los días y las dependencias
# casi nunca, así que de esta forma el pip install se salta en la mayoría de
# los builds y armar la imagen toma segundos en vez de minutos.
COPY requirements.txt requirements-dev.txt ./

# Instalamos también las de desarrollo (pytest, ruff, mypy) para poder correr
# los tests adentro del contenedor.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

# Ahora el código. Qué entra y qué no lo decide el .dockerignore.
#
# En desarrollo el compose monta la carpeta encima de esta copia, así que los
# cambios se ven al toque. Igual copiamos el código para que la imagen funcione
# sola y más adelante la podamos usar en el pipeline o en un servidor.
COPY . .

# El 8000 es el puerto por defecto de Django, por eso lo dejamos. Esta línea
# solo deja constancia; el que publica el puerto hacia tu máquina es el compose.
EXPOSE 8000

# Script que corre cada vez que arranca el contenedor. Espera a la base, aplica
# las migraciones y carga los datos demo.
#
# Lo llamamos con "sh" porque estamos todos en Windows y acá no existe el
# permiso de ejecución de Linux. Si no, el contenedor tiraría "permission
# denied" y habría que andar arreglándolo a mano.
ENTRYPOINT ["sh", "/app/entrypoint.sh"]

# Comando por defecto. Va separado del entrypoint para poder reemplazarlo sin
# tocar este archivo, por ejemplo con "docker compose run portal pytest" para
# correr los tests.
#
# El 0.0.0.0 es para poder entrar desde el navegador. Con 127.0.0.1 el
# contenedor se escucharía solo a sí mismo y no llegaríamos nunca.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
