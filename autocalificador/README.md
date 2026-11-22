# Autocalificador

Es **la misma rúbrica automática** con la que se evalúa tu entrega. Úsalo para comprobar tu avance antes de
entregar: lo que aquí marque en rojo es lo que te va a restar puntos.

## Qué necesitas

- Python 3.9 o superior.
- `git`, `gh` (GitHub CLI, con sesión iniciada: `gh auth login`) y `gcloud` (con sesión iniciada en la cuenta
  dueña de tu proyecto), todos en el `PATH`.
- `curl` (viene con macOS, Linux y Windows 10 o superior).

## Cómo correrlo

Desde la raíz de tu repositorio, en cualquier sistema:

```text
python autocalificador/grade.py --repo TU_USUARIO/TU_REPOSITORIO
```

(En macOS y Linux puede que el comando sea `python3`; en Windows, `py`.)

Lee `ENTREGA.yaml` de tu repositorio, prueba tu aplicación desplegada, revisa tu proyecto de Google Cloud
(solo lectura) y muestra el puntaje por categoría con el motivo de cada punto perdido.

## Qué revisa

Lo mismo que se describe en el enunciado y en la sección «Cómo se evalúa» del README: que la aplicación
funcione, que el repositorio no tenga secretos, que las dependencias no tengan vulnerabilidades conocidas,
que los secretos estén en Secret Manager y en uso, que todo esté en Terraform, que el pipeline exista y esté
en verde, y que el evaluador tenga los dos roles y `ENTREGA.yaml` esté completo.

## Importante

- Es un **piso**, no la nota final: la evaluación oficial la corre el evaluador sobre tu entrega y puede incluir
  revisiones adicionales. Pasar este script con 100 es necesario, pero la revisión final puede mirar más.
- No modifica nada en tu proyecto ni en tu repositorio.
- Si cambias este archivo, no cambia cómo te evalúan: la evaluación usa su propia copia.
