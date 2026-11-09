"""Check every blueprint: valid YAML, required metadata, a source_url that
points at its own path, and every !input it uses declared in its inputs."""
import glob
import sys

import yaml

REPO = "https://github.com/davidteles/ha-wall-panel-kit/blob/main/"


class Input(str):
    pass


class Loader(yaml.SafeLoader):
    pass


Loader.add_constructor("!input", lambda loader, node: Input(loader.construct_scalar(node)))


def declared(inputs):
    names = set()
    for key, value in (inputs or {}).items():
        if isinstance(value, dict) and "input" in value:  # a collapsible section
            names |= declared(value["input"])
        else:
            names.add(key)
    return names


def used(node):
    if isinstance(node, Input):
        yield str(node)
    elif isinstance(node, dict):
        for value in node.values():
            yield from used(value)
    elif isinstance(node, list):
        for value in node:
            yield from used(value)


errors = []
files = sorted(glob.glob("blueprints/**/*.yaml", recursive=True))
for path in files:
    try:
        doc = yaml.load(open(path, encoding="utf-8"), Loader=Loader)
    except yaml.YAMLError as err:
        errors.append(f"{path}: invalid YAML: {err}")
        continue
    meta = doc.get("blueprint") or {}
    for key in ("name", "description", "domain", "input", "source_url"):
        if key not in meta:
            errors.append(f"{path}: blueprint.{key} is missing")
    domain = path.split("/")[1]
    if meta.get("domain") != domain:
        errors.append(f"{path}: domain {meta.get('domain')!r} but it lives in blueprints/{domain}/")
    if meta.get("source_url") != REPO + path:
        errors.append(f"{path}: source_url should be {REPO + path}")
    missing = set(used(doc)) - declared(meta.get("input"))
    if missing:
        errors.append(f"{path}: uses undeclared inputs {sorted(missing)}")

print(f"{len(files)} blueprints checked")
for error in errors:
    print("ERROR", error)
sys.exit(1 if errors else 0)
