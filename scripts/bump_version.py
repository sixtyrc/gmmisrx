"""Actualiza filter_app/version.txt segun versionado semantico, a partir de los
commits (conventional commits) hechos desde la ultima vez que cambio la version.

Criterio:
  - MAJOR: un commit con "BREAKING CHANGE" o con "!" antes de ":" (ej. "feat!: ...")
  - MINOR: algun commit "feat"
  - PATCH: cualquier otro cambio (fix, perf, refactor, docs, chore, ...)

Uso (desde la raiz del repo, en dev, antes de pasar a prod):
  python scripts/bump_version.py           # calcula, escribe y commitea
  python scripts/bump_version.py --dry-run # solo muestra la nueva version
"""
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO = RAIZ / "filter_app" / "version.txt"
RUTA_GIT = "filter_app/version.txt"


def git(*args):
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, check=True).stdout


def commits_desde_ultima_version():
    ultimo = git("log", "-1", "--format=%H", "--", RUTA_GIT).strip()
    rango = f"{ultimo}..HEAD" if ultimo else "HEAD"
    salida = git("log", rango, "--format=%B%x00")
    return [c.strip() for c in salida.split("\x00") if c.strip()]


def tipo_de_cambio(commits):
    if any(re.match(r"^\w+(\(.*\))?!:", c) or "BREAKING CHANGE" in c for c in commits):
        return "major"
    if any(re.match(r"^feat(\(.*\))?:", c) for c in commits):
        return "minor"
    return "patch"


def siguiente(version, tipo):
    major, minor, patch = (int(x) for x in version.split("."))
    if tipo == "major":
        return f"{major + 1}.0.0"
    if tipo == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def main():
    actual = ARCHIVO.read_text(encoding="utf-8").strip()
    commits = commits_desde_ultima_version()
    if not commits:
        print(f"Sin cambios desde {actual}; no se actualiza.")
        return
    tipo = tipo_de_cambio(commits)
    nueva = siguiente(actual, tipo)
    print(f"{actual} -> {nueva} ({tipo}, {len(commits)} commits)")
    if "--dry-run" in sys.argv:
        return
    ARCHIVO.write_text(nueva + "\n", encoding="utf-8")
    git("add", RUTA_GIT)
    git("commit", "-m", f"chore(release): v{nueva}")


if __name__ == "__main__":
    main()
