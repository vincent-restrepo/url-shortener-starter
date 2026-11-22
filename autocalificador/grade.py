#!/usr/bin/env python3
"""Autocalificador del proyecto "Acortador de URLs en GCP".

Uso:
    python3 grade.py --repo OWNER/REPO [--json salida.json] [--keep]

Corre con la cuenta activa de gcloud (la del evaluador) y con `gh` autenticado.
Solo usa la biblioteca estándar; llama a git, gcloud, gh y curl.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

EVALUADOR = "user:vdrestrepot@unal.edu.co"
ROLES_EVALUADOR = {"roles/viewer", "roles/resourcemanager.projectDeleter"}

# Valores sembrados como trampa en el repo inicial
TRAMPAS = ["Qm7vX2pL9tRk4Wn8Zb3Y"]
TRAMPA_SHARED = re.compile(r'SHARED_SECRET["\']?\s*,\s*["\']([A-Za-z0-9_\-]{16,})["\']')
SECRETO_GENERICO = re.compile(
    r"(?i)(password|passwd|secret|api[_-]?key|token)[\"']?\s*[:=,(]\s*[\"']([A-Za-z0-9_\-/+=]{12,})[\"']"
)

RESULTADOS = []  # (categoria, puntos_obtenidos, puntos_max, [detalles])


def run(cmd, timeout=120, cwd=None):
    # shutil.which resuelve gcloud.cmd / curl.exe en Windows
    exe = shutil.which(cmd[0])
    if exe is None:
        return 99, "", f"no se encontró el programa «{cmd[0]}» en el PATH"
    try:
        p = subprocess.run(
            [exe, *cmd[1:]],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=cwd,
        )
        return p.returncode, p.stdout, p.stderr
    except (subprocess.TimeoutExpired, OSError) as e:
        return 99, "", str(e)


def gcloud_json(args, project=None):
    cmd = ["gcloud", *args, "--format=json", "--quiet"]
    if project:
        cmd += ["--project", project]
    rc, out, _ = run(cmd)
    if rc != 0:
        return None
    try:
        return json.loads(out or "null")
    except json.JSONDecodeError:
        return None


def curl(method, url, body=None, headers=None, follow=False):
    cmd = ["curl", "-sS", "-m", "30", "-o", "-", "-w", "\n%{http_code}", "-X", method]
    for k, v in (headers or {}).items():
        cmd += ["-H", f"{k}: {v}"]
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(body)]
    if follow:
        cmd.append("-L")
    cmd.append(url)
    rc, out, _ = run(cmd, timeout=40)
    if rc != 0 or "\n" not in out:
        return 0, ""
    text, _, code = out.rpartition("\n")
    return int(code or 0), text


def curl_headers(url):
    rc, out, _ = run(["curl", "-sS", "-m", "30", "-o", "/dev/null", "-D", "-", url], timeout=40)
    status = 0
    headers = {}
    for line in out.splitlines():
        if line.startswith("HTTP/"):
            parts = line.split()
            status = int(parts[1]) if len(parts) > 1 else 0
        elif ":" in line:
            k, _, v = line.partition(":")
            headers[k.strip().lower()] = v.strip()
    return status, headers


def categoria(nombre, maximo):
    detalles = []
    RESULTADOS.append([nombre, 0, maximo, detalles])
    return detalles


def otorgar(nombre, puntos):
    for r in RESULTADOS:
        if r[0] == nombre:
            r[1] = min(r[2], r[1] + puntos)


def parse_entrega(path):
    datos = {}
    if not path.exists():
        return datos
    for linea in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*([a-z_]+)\s*:\s*(.*?)\s*(#.*)?$", linea)
        if m:
            valor = m.group(2).strip().strip("\"'")
            datos[m.group(1)] = valor
    return datos


# ---------------------------------------------------------------- categorías


def check_entrega_y_acceso(entrega, project):
    nombre = "Acceso del evaluador y ENTREGA.yaml"
    d = categoria(nombre, 10)
    completos = bool(project) and bool(entrega.get("frontend_url", "").startswith("https://"))
    if completos:
        otorgar(nombre, 3)
        d.append("OK  ENTREGA.yaml completo (+3)")
    else:
        d.append("FALLA ENTREGA.yaml incompleto: faltan project_id o frontend_url https")
    if not project:
        return
    policy = gcloud_json(["projects", "get-iam-policy", project])
    if policy is None:
        d.append("FALLA no se pudo leer la política IAM del proyecto (¿sin acceso?)")
        return
    roles = {b["role"] for b in policy.get("bindings", []) if EVALUADOR in b.get("members", [])}
    if roles == ROLES_EVALUADOR:
        otorgar(nombre, 7)
        d.append("OK  el evaluador tiene exactamente los 2 roles (+7)")
    elif ROLES_EVALUADOR <= roles:
        otorgar(nombre, 4)
        d.append(f"PARCIAL roles de más para el evaluador: {sorted(roles - ROLES_EVALUADOR)} (+4)")
    else:
        d.append(f"FALLA roles del evaluador: {sorted(roles)}; faltan {sorted(ROLES_EVALUADOR - roles)}")


def check_funciona(frontend):
    nombre = "La aplicación funciona"
    d = categoria(nombre, 20)
    if not frontend:
        d.append("FALLA sin frontend_url")
        return
    base = frontend.rstrip("/")
    code, _ = curl("GET", base + "/health")
    if code == 200:
        otorgar(nombre, 3)
        d.append("OK  /health del frontend responde 200 (+3)")
    else:
        d.append(f"FALLA /health del frontend: {code}")
        return
    code, text = curl("GET", base + "/")
    if code == 200 and "<html" in text.lower():
        otorgar(nombre, 2)
        d.append("OK  el frontend sirve la página (+2)")
    else:
        d.append(f"FALLA la página principal: {code}")
    destino = "https://example.com/grader-" + str(int(time.time()))
    code, text = curl("POST", base + "/api/links", {"url": destino})
    try:
        creado = json.loads(text)
    except json.JSONDecodeError:
        creado = {}
    codigo = creado.get("code")
    if code in (200, 201) and codigo:
        otorgar(nombre, 5)
        d.append(f"OK  crear enlace por el frontend (+5) → {codigo}")
    else:
        d.append(f"FALLA crear enlace: {code} {text[:120]}")
        return
    status, headers = curl_headers(f"{base}/{codigo}")
    if status == 302 and headers.get("location") == destino:
        otorgar(nombre, 4)
        d.append("OK  el enlace corto redirige (302) al destino (+4)")
    else:
        d.append(f"FALLA redirección: {status} {headers.get('location')}")
    code, text = curl("GET", f"{base}/api/links/{codigo}/stats")
    try:
        clicks = json.loads(text).get("clicks", 0)
    except json.JSONDecodeError:
        clicks = 0
    if code == 200 and clicks >= 1:
        otorgar(nombre, 3)
        d.append(f"OK  las estadísticas cuentan clics ({clicks}) (+3)")
    else:
        d.append(f"FALLA estadísticas/clics: {code} clicks={clicks}")
    code, text = curl("GET", base + "/api/links")
    if code == 200 and codigo in text:
        otorgar(nombre, 3)
        d.append("OK  el listado incluye el enlace creado (+3)")
    else:
        d.append(f"FALLA listado: {code}")


def servicios_run(project):
    lista = gcloud_json(["run", "services", "list"], project) or []
    return lista


def check_backend_protegido(project):
    """Parte del puntaje de 'funciona' ya está repartido; esto va en secretos (backend cerrado)."""
    nombre = "Secretos en Secret Manager y en uso"
    d = categoria(nombre, 15)
    secretos = gcloud_json(["secrets", "list"], project)
    if secretos is None:
        d.append("FALLA no se pudo listar Secret Manager")
        return
    con_valor = []
    for s in secretos:
        sid = s["name"].split("/")[-1]
        vs = gcloud_json(["secrets", "versions", "list", sid], project) or []
        if any(v.get("state") == "ENABLED" for v in vs):
            con_valor.append(sid)
    if len(con_valor) >= 2:
        otorgar(nombre, 4)
        d.append(f"OK  {len(con_valor)} secretos con versión activa: {con_valor} (+4)")
    else:
        d.append(f"FALLA hay {len(con_valor)} secretos con versión activa (se esperan ≥ 2)")

    servicios = servicios_run(project)
    if not servicios:
        d.append("FALLA no se encontraron servicios de Cloud Run (¿otra plataforma?): revisión manual")
        return
    en_secreto, en_claro = set(), set()
    for s in servicios:
        for c in s.get("spec", {}).get("template", {}).get("spec", {}).get("containers", []):
            for e in c.get("env", []):
                nm = e.get("name", "")
                if nm in ("DB_PASSWORD", "SHARED_SECRET"):
                    if "secretKeyRef" in (e.get("valueFrom") or {}):
                        en_secreto.add(nm)
                    else:
                        en_claro.add(nm)
    if {"DB_PASSWORD", "SHARED_SECRET"} <= en_secreto and not en_claro:
        otorgar(nombre, 8)
        d.append("OK  DB_PASSWORD y SHARED_SECRET llegan por secretKeyRef, ninguna en claro (+8)")
    else:
        d.append(f"FALLA en secreto={sorted(en_secreto)} en claro={sorted(en_claro)}")

    cerrado = False
    for s in servicios:
        envs = {
            e.get("name")
            for c in s.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
            for e in c.get("env", [])
        }
        if "DB_PASSWORD" in envs and s.get("status", {}).get("url"):
            code, _ = curl("GET", s["status"]["url"].rstrip("/") + "/links")
            cerrado = code in (401, 403)
            d.append(f"    backend directo sin secreto → {code}")
    if cerrado:
        otorgar(nombre, 3)
        d.append("OK  el backend rechaza llamadas sin el secreto (+3)")
    else:
        d.append("FALLA el backend responde sin secreto o no se pudo comprobar")


def archivos_texto(raiz):
    for p in raiz.rglob("*"):
        if ".git" in p.parts or not p.is_file() or p.stat().st_size > 1_000_000:
            continue
        yield p


def check_secretos_repo(repo_dir):
    nombre = "El repositorio no contiene secretos"
    d = categoria(nombre, 15)
    hallazgos = []
    for p in archivos_texto(repo_dir):
        if p.suffix in {".png", ".jpg", ".ico", ".lock", ".pyc"}:
            continue
        if "tests" in p.parts or p.name == "conftest.py":
            continue  # valores ficticios de pruebas
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = p.relative_to(repo_dir)
        for t in TRAMPAS:
            if t in txt:
                hallazgos.append(f"{rel}: valor sembrado de DB_PASSWORD")
        for m in TRAMPA_SHARED.finditer(txt):
            hallazgos.append(f"{rel}: valor por defecto de SHARED_SECRET")
        if p.suffix in {".py", ".tf", ".yaml", ".yml", ".json", ".env", ".sh", ""} and rel.name != "README.md":
            for m in SECRETO_GENERICO.finditer(txt):
                v = m.group(2)
                if not re.search(r"(?i)(example|changeme|dummy|test|dev|local|secret_id|var\.)", v + m.group(0)):
                    hallazgos.append(f"{rel}: posible secreto «{m.group(1)}»")
    if (repo_dir / "terraform").exists():
        for p in (repo_dir / "terraform").rglob("*.tfstate*"):
            hallazgos.append(f"{p.relative_to(repo_dir)}: archivo de state en el repo")
        for p in (repo_dir / "terraform").rglob("*.tfvars"):
            hallazgos.append(f"{p.relative_to(repo_dir)}: tfvars en el repo (revisar)")
    unicos = sorted(set(hallazgos))
    if not unicos:
        otorgar(nombre, 15)
        d.append("OK  el árbol de trabajo no tiene secretos (+15)")
    else:
        d += [f"FALLA {h}" for h in unicos[:15]]


def check_dependencias(repo_dir):
    nombre = "Dependencias sin vulnerabilidades"
    d = categoria(nombre, 10)
    paquetes = []
    for req in repo_dir.rglob("requirements*.txt"):
        if ".git" in req.parts or ".venv" in req.parts:
            continue
        if req.name.startswith("requirements-dev"):
            continue
        for linea in req.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\s*([A-Za-z0-9_.\-]+)\s*==\s*([A-Za-z0-9_.\-+]+)", linea)
            if m:
                paquetes.append((m.group(1), m.group(2), req.relative_to(repo_dir)))
    if not paquetes:
        d.append("FALLA no se encontraron dependencias fijadas (==) en requirements.txt")
        return
    consulta = {"queries": [{"package": {"name": n, "ecosystem": "PyPI"}, "version": v} for n, v, _ in paquetes]}
    rc, out, err = run(
        ["curl", "-sS", "-m", "60", "-X", "POST", "https://api.osv.dev/v1/querybatch", "-d", json.dumps(consulta)],
        timeout=90,
    )
    try:
        res = json.loads(out)["results"]
    except (json.JSONDecodeError, KeyError):
        d.append(f"FALLA no se pudo consultar OSV: {err[:100]}")
        return
    malas = []
    for (n, v, f), r in zip(paquetes, res):
        ids = [x["id"] for x in r.get("vulns", [])]
        if ids:
            malas.append(f"{n}=={v} ({f}): {len(ids)} vulnerabilidades, p. ej. {ids[0]}")
    if not malas:
        otorgar(nombre, 10)
        d.append(f"OK  {len(paquetes)} dependencias sin vulnerabilidades conocidas (+10)")
    else:
        d += [f"FALLA {m}" for m in malas]


def estado_terraform(project):
    buckets = gcloud_json(["storage", "buckets", "list"], project) or []
    for b in buckets:
        nombre = b.get("name") or b.get("id")
        rc, out, _ = run(["gcloud", "storage", "ls", "-r", f"gs://{nombre}/**", "--project", project, "--quiet"])
        for linea in out.splitlines():
            if linea.endswith(".tfstate"):
                rc, contenido, _ = run(["gcloud", "storage", "cat", linea, "--project", project])
                try:
                    return nombre, json.loads(contenido)
                except json.JSONDecodeError:
                    continue
    return None, None


def check_terraform(repo_dir, project):
    nombre = "Todo está en Terraform"
    d = categoria(nombre, 15)
    tf = list((repo_dir / "terraform").glob("*.tf")) if (repo_dir / "terraform").exists() else []
    if not tf:
        d.append("FALLA no hay archivos .tf en terraform/")
        return
    otorgar(nombre, 2)
    d.append(f"OK  {len(tf)} archivos .tf en terraform/ (+2)")
    contenido = "\n".join(p.read_text(encoding="utf-8") for p in tf)
    if re.search(r'backend\s+"gcs"', contenido):
        otorgar(nombre, 2)
        d.append("OK  backend remoto en GCS (+2)")
    else:
        d.append("FALLA no declara backend gcs")
    bucket, estado = estado_terraform(project)
    if not estado:
        d.append("FALLA no se encontró un state legible en el proyecto")
        return
    recursos = [r for r in estado.get("resources", []) if r.get("mode") == "managed"]
    tipos = {r["type"] for r in recursos}
    d.append(f"    state en gs://{bucket} con {len(recursos)} recursos")
    otorgar(nombre, 3)
    d.append("OK  state legible con recursos (+3)")
    esperados = {
        "secretos": "google_secret_manager_secret",
        "base de datos": "google_sql_database_instance",
        "cómputo": ("google_cloud_run_v2_service", "google_cloud_run_service", "google_container_cluster"),
        "acceso evaluador": "google_project_iam_member",
    }
    for etiqueta, t in esperados.items():
        ok = bool(tipos & set(t)) if isinstance(t, tuple) else t in tipos
        if ok:
            otorgar(nombre, 1)
            d.append(f"OK  {etiqueta} gestionado por Terraform (+1)")
        else:
            d.append(f"FALLA {etiqueta} no aparece en el state")
    # nada creado a mano: servicios y secretos del proyecto vs state
    ids_state = json.dumps(estado)
    huerfanos = []
    for s in servicios_run(project):
        n = s["metadata"]["name"]
        if f'"{n}"' not in ids_state:
            huerfanos.append(f"Cloud Run {n}")
    for s in gcloud_json(["secrets", "list"], project) or []:
        n = s["name"].split("/")[-1]
        if f'"{n}"' not in ids_state:
            huerfanos.append(f"secreto {n}")
    if not huerfanos:
        otorgar(nombre, 4)
        d.append("OK  los servicios y secretos del proyecto están todos en el state (+4)")
    else:
        d.append(f"FALLA recursos fuera de Terraform: {huerfanos}")
    # secretos en claro dentro del state ya no se penalizan: se advierte en el README
    # (los valores generados por Terraform quedan en el state)
    if not re.search(r"(?i)(allUsers|allAuthenticatedUsers)", contenido):
        pass


def check_pipeline(repo_dir, repo):
    nombre = "Pipeline de GitHub Actions"
    d = categoria(nombre, 15)
    wfs = list((repo_dir / ".github" / "workflows").glob("*.y*ml")) if (repo_dir / ".github").exists() else []
    if not wfs:
        d.append("FALLA no hay workflows en .github/workflows/")
        return
    texto = "\n".join(p.read_text(encoding="utf-8").lower() for p in wfs)
    otorgar(nombre, 2)
    d.append(f"OK  {len(wfs)} workflow(s) (+2)")
    pruebas = {
        "lint": (r"ruff|flake8|pylint|black --check", 3),
        "vulnerabilidades": (r"trivy|grype|pip-audit|safety|snyk|osv-scanner|checkov|gitleaks", 3),
        "build": (r"docker build|docker/build-push-action|gcloud builds|pack build|buildx", 3),
    }
    for etiqueta, (rx, pts) in pruebas.items():
        if re.search(rx, texto):
            otorgar(nombre, pts)
            d.append(f"OK  paso de {etiqueta} (+{pts})")
        else:
            d.append(f"FALLA no se detecta paso de {etiqueta}")
    if "continue-on-error: true" in texto or re.search(r"exit-code:\s*['\"]?0", texto):
        d.append("FALLA el pipeline silencia errores (continue-on-error / exit-code 0)")
    else:
        otorgar(nombre, 1)
        d.append("OK  no silencia errores (+1)")
    rc, out, err = run(
        ["gh", "api", f"repos/{repo}/actions/runs?branch=main&per_page=1", "--jq", ".workflow_runs[0].conclusion"]
    )
    conclusion = out.strip()
    if rc == 0 and conclusion == "success":
        otorgar(nombre, 3)
        d.append("OK  la última ejecución en main está en verde (+3)")
    else:
        d.append(f"FALLA última ejecución en main: {conclusion or err.strip()[:100] or 'ninguna'}")


# ---------------------------------------------------------------- principal


def evaluar(repo, project=None, frontend=None, keep=False, despues=None):
    """Clona el repo, corre todos los checks y devuelve el resultado.

    `despues(ctx)` se llama con el clon todavía disponible; ctx es un dict con
    repo, repo_dir, entrega, project y frontend.
    """
    del RESULTADOS[:]
    tmp = Path(tempfile.mkdtemp(prefix="grader-"))
    repo_dir = tmp / "repo"
    rc, _, err = run(["gh", "repo", "clone", repo, str(repo_dir), "--", "--quiet"], timeout=180)
    if rc != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        sys.exit(f"No se pudo clonar {repo}: {err.strip()}")
    try:
        entrega = parse_entrega(repo_dir / "ENTREGA.yaml")
        if project:
            entrega["project_id"] = project
        if frontend:
            entrega["frontend_url"] = frontend
        project = entrega.get("project_id", "")
        if project.upper().startswith("TU_") or project == "":
            project = ""
        frontend = entrega.get("frontend_url", "")

        check_funciona(frontend)
        check_secretos_repo(repo_dir)
        check_dependencias(repo_dir)
        if project:
            check_backend_protegido(project)
            check_terraform(repo_dir, project)
        else:
            categoria("Secretos en Secret Manager y en uso", 15).append("FALLA sin project_id")
            categoria("Todo está en Terraform", 15).append("FALLA sin project_id")
        check_pipeline(repo_dir, repo)
        check_entrega_y_acceso(entrega, project)
        ctx = {"repo": repo, "repo_dir": repo_dir, "entrega": entrega, "project": project, "frontend": frontend}
        extra = despues(ctx) if despues else None
    finally:
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)
    return {
        "repo": repo,
        "project": project,
        "total": sum(r[1] for r in RESULTADOS),
        "max": sum(r[2] for r in RESULTADOS),
        "categorias": [{"nombre": n, "puntos": p, "max": m, "detalles": dt} for n, p, m, dt in RESULTADOS],
        "extra": extra,
    }


def imprimir(res):
    print(f"\nRepo: {res['repo']}   Proyecto: {res['project'] or '—'}\n")
    for c in res["categorias"]:
        print(f"== {c['nombre']}: {c['puntos']}/{c['max']}")
        for linea in c["detalles"]:
            print("   " + linea)
    print(f"\nTOTAL: {res['total']}/{res['max']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="USUARIO/REPO de tu fork")
    ap.add_argument("--json", help="guardar el resultado en este archivo")
    ap.add_argument("--project", help="sobrescribe project_id (pruebas)")
    ap.add_argument("--frontend", help="sobrescribe frontend_url (pruebas)")
    ap.add_argument("--keep", action="store_true", help="no borrar el clon temporal")
    args = ap.parse_args()
    res = evaluar(args.repo, args.project, args.frontend, args.keep)
    imprimir(res)
    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
