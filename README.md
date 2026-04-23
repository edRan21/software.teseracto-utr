# Software.Teseracto-UTR

<h1>Bienvenido al repositorio en donde se almacena el sistema de telemetría Teseracto UTR (Unidad de transmisión remota)</h1>

<ul>
    <li>
        <h2>¿Que es?</h2>
    </li>
    <p>Es una herramienta de medición automatizada conocida entre los sistemas de medición como <b>telemetría</b>. Su proposito es (por el momento) monitoreo industrial, ya que este se comunica con dispositivos de comunicación indutrial como Modbus RTU (con la posibilidad de escalar más protocolos) para leer datos de los dispositivos que puedan hacerlo y exista documentación como el mapa de memoria del dispositivo que permita conocer el registro de su memoria donde almacene el dato que se desea leer</p>
</ul>

<h2>Aspectos a seguir para conocer el entorno de desarrollo del sistema y su configuración local</h2>

<p>Clona el repositorio en tu maquina local con:</p>

    git clone https://github.com/edRan21/software.teseracto-utr.git

<i>Asegurate de estar dentro del repositorio ya que este es privado, cualquier problema técnico comunicalo al administrador</i>

<i>Asegurese de no arrastrar o clonar el repositorio con la carpeta del entorno virtual creado "venv", ya que esta puede generar conflictos con las rutas de ejecución del proyecto, al clonar el repositorio usted mismo debe crear un entorno virtual, tener Python 3.13.2 como versión e instalar las librerias utilizadas con:<i>

```
python -m venv venv
```

```
.\venv\Scripts\activate
```

```
python -m pip install --upgrade pip
```

```
pip install -r requirements.txt
```

Si desea realizar pruebas desde el entorno de desarrollo ejecute el siguiente comando:

```
python -m GUI.App
```

El modificador "-m" va a ejecutar un modulo completo en el que se definen las demás rutas a las cuales el punto de entrada (el script App.py) esta conectado, o sea a todo el sistema, por lo que estos los tratará como paquetes, gracias a que en cada directorio del proyecto están esparcidos los archivos __init__.py 

El comando para empaquetar es:

```
pyinstaller TESSERACTO-UTR.spec
```

<p>Hacemos uso de la librería de pyinstaller para compilar y generar un ejecutable, <b>es importante que copies manualmente las images y los archivos de configuración .JSON a las carpetas que le corresponden ya que el sistema se quejará si no encuentra estos recursos para inicializar</b></p>