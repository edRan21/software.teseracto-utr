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

<i>Asegurese de no arrastrar o clonar el repositorio con la carpeta del entorno virtual creado "venv", ya que esta puede generar conflictos con las rutas de ejecución del proyecto, al clonar el repositorio usted mismo debe crear un entorno virtual, tener Python 3.13.2 como versión e instalar las librerias utilizadas con:</i>

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

>[!WARNING]
>Al ejecutar el siguiente comando recordar que este se encarga de tomar todas la librerias instaladas y utilizadas en tu entorno local o en tu entorno virtual y crear un archivo con el que python podra utilizar para instalar de un solo golpe todas las bibliotecas del proyecto, CUIDADO, si tienes alguna otra libreria que no este siendo utilizada por el proyecto puede que el comando lo agregue en el archivo requirements.txt (ESTE Y TODOS LOS ANTERIORES COMANDOS DEBEN SER ESTUDIADOS PARA SU COMPRESIÓN):
>
> pip freeze > requirements.txt


>[!NOTE]
>Utiliza el siguiente comando para automatizar la tarea de compilar el software y generar un empaquetamiento limpio de cualquier cache que interfiera con los paquetes del sistema.
>
> ./build.bat
>
>Recomendable utilizar este comando si continuamente empaqueta el software tras cada nueva integración que realice (es un script que automatiza la tarea de empaquetar el software con el .spec para pyinstaller de forma limpia y elimina el .exe que queda en la raiz de 'build/' ).

Una vez que genere la carpeta <i>build/</i> junto con el programa del sistema de UTR, genere el instalador ejecutando el programa <i>instalador_TESSERACTO-UTR.exe</i>
Cualquier modificación al instalador se realiza en el script de la raiz del proyecto NSIS <i>installer.nsi</n>, asegurese de tener instalado la extensión en VSCode de NSIS, los softwares de NSIS y HM NIS EDIT.
Links de descarga:
- [NSIS: Archivos de sistema de instalación scriptable Nullsoft](https://sourceforge.net/projects/nsis/files/NSIS%203/3.12/nsis-3.12-setup.exe/download?use_mirror=cfhcable&download)
- [HM NIS EDTI](https://sourceforge.net/projects/hmne/files/HM%20NIS%20Edit/2.0.3/nisedit2.0.3.exe/download?use_mirror=psychz&download)

Si lo require, aquí podra escoger la versión de NSIS que desee instalar:
- [versiones de NSIS, en la sección de 'files'](https://sourceforge.net/projects/nsis/files/NSIS%202/)

Documentación de NSIS (sintaxis, herramientas, complementos):
- [NSIS Docs/contents](https://nsis.sourceforge.io/Docs/Contents.html)

>[!IMPORTANT]
>Debe de asegurarse que después de empaquetar el software, se le debe generar un directorio en la raíz del proyecto llamado 'build/', donde dentro se encuentre el directorio 'TESSERACTO-UTR/' y que dentro guarde el ejecutable 'TESSERACTO-UTR.exe' y un directorio con las dependencias, binarios y recursos que utiliza el sistema llamado '_internal/'
