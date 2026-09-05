# Atajos para las tareas repetitivas del proyecto.
#
# La gracia es que los mismos comandos que corren acá son los que corre el
# pipeline. Si "make calidad" pasa en tu máquina, el pipeline va a pasar.
# Evita el clásico "en mi computador funcionaba".
#
# Uso: make instalar, make correr, make calidad
#
# IMPORTANTE: este archivo funciona en Linux y macOS. En Windows no, por dos
# razones: "make" no viene instalado, y el entorno virtual pone los ejecutables
# en .venv\Scripts\ en vez de .venv/bin/.
#
# En Windows se corren los comandos sueltos. Primero se activa el entorno:
#
#   .venv\Scripts\activate.bat
#
# y después, el equivalente de cada objetivo de este archivo:
#
#   make instalar  ->  py -3.12 -m venv .venv
#                      pip install -r requirements.txt -r requirements-dev.txt
#   make correr    ->  python manage.py runserver
#   make migrar    ->  python manage.py migrate
#   make lint      ->  ruff check --fix . && ruff format .
#   make tipos     ->  mypy .
#   make test      ->  set "USE_SQLITE=1" && pytest --cov=. --cov-report=term-missing
#
# Las comillas en set "USE_SQLITE=1" no son opcionales: sin ellas la consola de
# Windows guarda el valor con un espacio al final y los tests intentan
# conectarse a MariaDB en vez de usar SQLite.

PYTHON = .venv/bin/python
PIP = .venv/bin/pip

instalar:  ## Crea el entorno virtual e instala todas las dependencias
	python3 -m venv .venv
	$(PIP) install -r requirements.txt -r requirements-dev.txt

correr:  ## Levanta el servidor de desarrollo en localhost:8000
	$(PYTHON) manage.py runserver

migrar:  ## Aplica los cambios pendientes del modelo de datos a la base
	$(PYTHON) manage.py migrate

migraciones:  ## Genera los archivos de migración tras cambiar un modelo
	$(PYTHON) manage.py makemigrations

lint:  ## Revisa estilo y errores obvios, y formatea el código
	.venv/bin/ruff check --fix .
	.venv/bin/ruff format .

tipos:  ## Verifica los tipos sin ejecutar el código
	.venv/bin/mypy .

test:  ## Corre los tests y reporta la cobertura
	$(PYTHON) -m pytest --cov=. --cov-report=term-missing

calidad: lint tipos test  ## Corre todo lo que corre el pipeline

.PHONY: instalar correr migrar migraciones lint tipos test calidad
