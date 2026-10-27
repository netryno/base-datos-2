import json, time, redis
from pymongo import MongoClient
 
r  = redis.Redis(host="localhost", port=6379, password="123456", decode_responses=True)
db = MongoClient("mongodb://localhost:27017")["bd_educacion"]
 
def get_asignatura(codigo):
    clave = f"asignatura:{codigo}"
    cache = r.get(clave)                  # 1. ¿está en Redis?
    if cache:
        return json.loads(cache), "CACHE"  # HIT
    doc = db.asignatura.find_one({"codigo": codigo}, {"_id": 0})  # 2. MISS: BD
    r.set(clave, json.dumps(doc), ex=60)    # 3. guardar 60 s
    return doc, "BD"


for _ in range(3):
    t = time.perf_counter()
    _, origen = get_asignatura("SIS-221")
    print(origen, round((time.perf_counter()-t)*1000, 1), "ms")


ejemplo salida
BD     12.4 ms
CACHE   0.6 ms
CACHE   0.5 ms


Requiero inmplentar una interface donde se va esta ingregacion mongo y redis y mostrar a los alumnos tiempos
En el .env ira los variables de conexion de bd.
sera un widget que mostrar esos datos de salida, y un boton para dispara evento y mostrar tiempos.


con un boton cosuma info de la bd y su rescpetivo tiempo y de redis y su respectivo tiempo.
(practicamente estructura simple de cacheo de informacion , si dicho data no esta en redis vaya hasta backend, si no desde redis responder. )

Hasta ahi serial el widget desmostrativo para explicar redis.

Luego un segundo widget donde se esoca ser publicador en redis.
> PUBLISH chat:sala1 "Hola desde T2"
(integer) 1
 
# 1 = un oyente lo recibió


en ese mismo widget si escoge ser suscriptor:
> SUBSCRIBE chat:sala1
1) "subscribe"
2) "chat:sala1"
3) (integer) 1
 
1) "message"
2) "chat:sala1"
3) "Hola desde T2"


seria practicamente algo como para filas de atension a cliente (banco), pero unicamente en el widget comunicariamos que ficha le toca turno, desde el publicador, a los suscriptores (que puedes ser varios), Etnonces al momento de ingresar en la interface escogerian si ser suscrito o publicador , solo uno pude ser publicaddor, eso tb como usar redise para usar uno solo valor con (SET lock:oferta "activa" NX EX 30, supongo que ahi podnria limitado ese canal coupado y ya no pdiera otro)

y los suscriptores posibldad de suscribire y en widget todo lo que ponga en el widget publicador verian, limitamos a texto cortos para evitar saturacion de pantalla.

otro widget , donde el publicador tenga su mapa en leaflet y marcador.
en widget de suscritor veriala mapa , cuaando el publicador mueba la mapa , se mueva en los suscritores.



esos 3 widget ajusta para que se lo mas simple pero a la vez lo mas academico sin saturar mucho.


la conexion a mongo, ya esta en otro docker
MONGO_URI=mongodb://admin:123456@mongo:27017/?authSource=admin

la conxion a redis ya esta en otro docker:
docker exec -it redis-d redis-cli -a 123456