# Acortador de enlaces

Un acortador de URLs como los que usas todos los días: pegas una dirección larga, obtienes una corta, y la
plataforma cuenta cuántas veces se abre.

Es un **proyecto académico que simula un proyecto real de trabajo**. Recibes el código de una aplicación
que ya funciona, y tu trabajo es lo que un equipo de ingeniería haría antes de ponerla en producción:
**decidir dónde y cómo se despliega en Google Cloud, hacerlo con Terraform, manejar bien sus secretos y
automatizar los cambios con un pipeline.** El resultado debe ser una aplicación funcional, accesible desde
internet.

---

## 1. Qué recibes

```text
.
├── app/
│   ├── backend/         # API REST + acceso a PostgreSQL
│   ├── frontend/        # página web + reenvío de las llamadas al backend
│   └── requirements-dev.txt
├── autocalificador/     # la rúbrica automática, para que te autocorrijas antes de entregar
├── terraform/           # aquí va TODO tu Terraform
├── ENTREGA.yaml         # los datos de tu despliegue, para el autocalificador
└── README.md
```

Haz un **fork** de este repositorio. Tu fork es tu entrega.

> ⚠️ GitHub **desactiva GitHub Actions por defecto en los forks**. Entra a la pestaña *Actions* de tu fork
> y actívalo antes de crear tu pipeline, o no se ejecutará nada.

---

## 2. Cómo funciona la aplicación

Dos servicios y una base de datos. La gente solo habla con el frontend; el backend no debería recibir
llamadas que no vengan de él.

```mermaid
flowchart LR
    user(["Persona<br/>con navegador"])
    web["<b>Frontend</b><br/>sirve la página<br/>y reenvía las llamadas"]
    api["<b>Backend</b><br/>API REST<br/>reglas de negocio"]
    db[("<b>PostgreSQL</b>")]

    user -->|HTTPS| web
    web -->|"HTTPS + cabecera<br/>X-Shared-Secret"| api
    api -->|"usuario + contraseña"| db
```

> Este diagrama es **lógico**: dice qué se comunica con qué, no dónde corre cada pieza. Esa decisión
> es tuya.

### Qué pasa cuando alguien usa la app

```mermaid
sequenceDiagram
    actor P as Persona
    participant W as Frontend
    participant A as Backend
    participant D as PostgreSQL

    Note over P,D: Acortar un enlace
    P->>W: POST /api/links {url}
    W->>A: POST /links + X-Shared-Secret
    A->>A: ¿secreto correcto? ¿URL válida?
    A->>D: INSERT (código, url)
    A-->>W: 201 {código}
    W-->>P: enlace corto

    Note over P,D: Abrir un enlace corto
    P->>W: GET /abc123
    W->>A: GET /abc123 + X-Shared-Secret
    A->>D: UPDATE clicks = clicks + 1
    A-->>W: 302 → url original
    W-->>P: 302 → te lleva al destino

    Note over P,A: Llamada directa al backend (no debe funcionar)
    P->>A: GET /links (sin secreto)
    A-->>P: 401
```

### API del backend

Todas las rutas, salvo `/health`, exigen la cabecera `X-Shared-Secret`.

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Estado del servicio (sin autenticación) |
| `POST` | `/links` | Crea un enlace. Cuerpo: `{"url": "https://..."}` |
| `GET` | `/links` | Últimos 50 enlaces con sus clics |
| `GET` | `/links/{code}/stats` | Estadísticas de un enlace |
| `GET` | `/{code}` | Redirige (302) al destino y suma un clic |

---

## 3. Lo que necesita cada servicio para funcionar

Este es el contrato. **Cómo y dónde lo proporcionas es decisión tuya.**

| | Backend | Frontend |
|---|---|---|
| **Instalar** | `pip install -r requirements.txt` | `pip install -r requirements.txt` |
| **Arrancar** (desde su carpeta) | `uvicorn main:app --host 0.0.0.0 --port $PORT` | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| **Python** | 3.11 | 3.11 |
| **Variables de entorno** | `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `SHARED_SECRET` | `BACKEND_URL`, `SHARED_SECRET` |
| **Base de datos** | PostgreSQL accesible desde el backend | no la usa |
| **Salud** | `GET /health` → 200 | `GET /health` → 200 |

Notas:
- `$PORT` es una variable de entorno con el puerto en el que debe escuchar el servicio (en PowerShell se
  escribe `$env:PORT`).
- **Este repositorio no incluye Dockerfile.** Si la plataforma que elijas necesita contenedores, escribir la
  imagen es parte de tu trabajo; la tabla de arriba te dice cómo arranca cada servicio.
- `DB_HOST` puede ser un nombre de host o la ruta de un socket Unix (por ejemplo `/cloudsql/...`).
  Si no la defines, el valor por defecto es `localhost`. Valores por defecto de `DB_NAME` y `DB_USER`:
  `shortener`.
- El backend **crea su propia tabla** al arrancar; no necesitas migraciones.
- `SHARED_SECRET` debe ser **el mismo valor** en el frontend y en el backend.
- `BACKEND_URL` es la dirección base del backend, por ejemplo `https://mi-backend.example.com`.

---

## 4. Lo que tienes que hacer

**Requisitos previos:** una cuenta de Google Cloud con facturación, `gcloud`, `terraform` (≥ 1.9), `git` y
una cuenta de GitHub. Para que Terraform pueda actuar en tu nombre, ejecuta una vez
`gcloud auth application-default login`.

**Lo único que se hace a mano** (todo lo demás, incluido habilitar las APIs, es Terraform):

1. Crear el proyecto de Google Cloud y vincularle la facturación.
2. Crear el bucket donde Terraform guardará su *state*. Terraform no puede crear el bucket que él mismo
   necesita para arrancar.

**El trabajo:**

1. **Desplegar la aplicación en Google Cloud**, accesible desde internet. Tú decides qué servicios de
   Google Cloud usar para el frontend, el backend y la base de datos.
2. **Hacerlo todo con Terraform**, dentro de la carpeta `terraform/`. Si un recurso no está ahí, no cuenta.
   El *state* va en el bucket de Cloud Storage del paso manual 2.
3. **Manejar los secretos como se hace en un entorno real.** Los valores sensibles no pueden vivir en el
   código ni en el repositorio, y los secretos se gestionan con **Secret Manager**.
4. **Crear un pipeline en GitHub Actions** (`.github/workflows/`). En cada cambio debe, como mínimo:
   revisar el estilo del código, buscar vulnerabilidades y construir la aplicación. **Si encuentra un
   problema, el pipeline debe fallar.** El pipeline *no* necesita desplegar nada en Google Cloud. En tu
   entrega final, la última ejecución en la rama `main` debe estar en verde.
5. **Darle acceso al evaluador, también con Terraform.** Es obligatorio y tiene su propia sección: la 5.
6. **Completar `ENTREGA.yaml`** con el ID de tu proyecto y la URL pública del frontend.

> 💡 Al habilitar APIs con Terraform, el primer `terraform apply` puede fallar con un error `403` o
> `IAM_PERMISSION_DENIED` en el recurso que sigue (por ejemplo, Artifact Registry): el API recién habilitado
> tarda unos segundos en propagarse. No es un error de tu código; espera un minuto y vuelve a ejecutar
> `terraform apply`. Si defines `depends_on` hacia el recurso que habilita el API, ocurre menos.

Tu proyecto tiene que **funcionar**: se podrán crear enlaces desde el frontend, abrirlos y ver sus clics.

**Cuida el costo.** Algunos servicios cobran por hora mientras existan (una base de datos Cloud SQL es el
caso típico). Crea una alerta de presupuesto en tu proyecto y destruye la infraestructura cuando no la
estés usando.

---

## 5. Dar acceso al evaluador (obligatorio)

Para poder calificar tu despliegue y destruirlo al terminar, el evaluador necesita entrar a **tu proyecto de
Google Cloud**. Eres tú quien se lo concede, **con Terraform** y dentro de la carpeta `terraform/`.

**La cuenta del evaluador** (cópiala, no la teclees):

```text
vdrestrepot@unal.edu.co
```

En IAM se escribe como miembro de tipo usuario: `user:vdrestrepot@unal.edu.co`.

**Los roles que debes concederle, y solo estos dos:**

| Rol | Para qué lo necesita |
|---|---|
| `roles/viewer` | Leer la configuración de tu infraestructura y tu *state*, para comprobar lo que hiciste. |
| `roles/resourcemanager.projectDeleter` | Borrar el proyecto completo cuando termine la evaluación. |

**Lo que NO debes darle:**

- Ningún otro rol, y menos `roles/owner` o `roles/editor`.
- Acceso para leer secretos en Secret Manager (`roles/secretmanager.secretAccessor`). El evaluador comprueba
  que tus secretos existen y tienen valor, pero **nunca necesita leerlos**.

> **Sobre el *state*.** `roles/viewer` permite leer el bucket donde está tu *state*, y el *state* de Terraform
> puede guardar en texto plano los valores que Terraform genera (contraseñas, por ejemplo). Por eso el bucket
> del *state* nunca debe ser público, y por eso es importante entender qué guarda cada recurso.

**Cómo comprobar que lo hiciste bien.** Este comando debe mostrar exactamente esos dos roles, ni más ni menos:

```text
gcloud projects get-iam-policy TU_PROYECTO --flatten="bindings[].members" --filter="bindings.members:vdrestrepot@unal.edu.co" --format="value(bindings.role)"
```

(Es un solo comando en una línea: funciona igual en macOS, Linux y Windows.)

**Qué va a pasar con tu proyecto.** Cuando termine la evaluación, el evaluador **borrará el proyecto
entero** con el rol `projectDeleter`. No guardes ahí nada que quieras conservar. Google mantiene un proyecto
borrado durante 30 días antes de eliminarlo definitivamente, y deja de cobrarte desde el momento del
borrado.

**Dale el acceso *antes* de entregar.** Sin estos permisos no se puede evaluar tu despliegue.

---

## 6. Correrlo en tu máquina

Necesitas Python 3.11, Docker (Docker Desktop en Windows y macOS) y tres terminales. Los comandos cambian
según tu sistema; en Windows también puedes usar WSL y seguir la versión de Linux.

**Primero, la base de datos** (igual en todos los sistemas):

```text
docker run -d --name pg -p 5432:5432 -e POSTGRES_USER=shortener -e POSTGRES_PASSWORD=dev -e POSTGRES_DB=shortener postgres:15
```

### macOS y Linux (bash o zsh)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r app/requirements-dev.txt

# Terminal 1 (activa el entorno virtual: source .venv/bin/activate)
cd app/backend
DB_PASSWORD=dev SHARED_SECRET=secreto-local uvicorn main:app --port 8001

# Terminal 2 (activa el entorno virtual otra vez)
cd app/frontend
SHARED_SECRET=secreto-local BACKEND_URL=http://localhost:8001 uvicorn main:app --port 8000
```

### Windows (PowerShell)

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r app/requirements-dev.txt

# Terminal 1 (activa el entorno virtual: .venv\Scripts\Activate.ps1)
cd app\backend
$env:DB_PASSWORD="dev"; $env:SHARED_SECRET="secreto-local"
uvicorn main:app --port 8001

# Terminal 2 (activa el entorno virtual otra vez)
cd app\frontend
$env:SHARED_SECRET="secreto-local"; $env:BACKEND_URL="http://localhost:8001"
uvicorn main:app --port 8000
```

Si PowerShell no deja activar el entorno virtual, ejecuta una vez
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

Abre <http://localhost:8000>. Los tests no necesitan base de datos (desde la raíz del repositorio, con el
entorno virtual activo; en cualquier sistema):

```text
pytest app/backend/tests
pytest app/frontend/tests
ruff check app/
```

---

## 7. Cómo se evalúa

La evaluación es **automática** y se hace sobre tu repositorio y sobre tu despliegue en funcionamiento. En
términos generales se revisa que:

- la aplicación funcione desde la URL que entregaste,
- el repositorio no contenga secretos,
- los secretos estén en Secret Manager y la aplicación los use,
- las dependencias no tengan vulnerabilidades conocidas graves,
- toda la infraestructura esté definida en Terraform,
- el pipeline exista, bloquee los cambios con problemas y su última ejecución en `main` esté en verde,
- el evaluador tenga **exactamente** los dos roles de la sección 5,
- `ENTREGA.yaml` esté completo.

Puedes comprobar tu avance cuando quieras con el **autocalificador** de la carpeta `autocalificador/`
(instrucciones en su `README.md`). Es la misma rúbrica automática: es un piso, y la revisión final puede
incluir comprobaciones adicionales.

Al terminar la evaluación, el proyecto se borra (sección 5).
