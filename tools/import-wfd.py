#!/usr/bin/env python3
"""Imports APIs from the Web Fuzzing Dataset (WFD) into apis/.

Reads the WFD checkout in upstream/wfd (a git submodule) and writes, for each API, a folder
apis/<name>/ that runs without the submodule:

  compose.yaml   WFD's compose file without its recording proxy, every image pinned by digest,
                 the API published on an ephemeral port of 127.0.0.1, and the dataset's own
                 description of the API under the top-level key x-dataset
  openapi.*      WFD's copy of the API's document
  auth.yaml      WFD's credentials for the API, in Web Fuzzing Commons format, when it has any
  files/         the seed and configuration files the compose file mounts

Usage:
  tools/import-wfd.py                 every REST API WFD packages
  tools/import-wfd.py petclinic-rest  only the ones named

Needs Docker (docker compose and docker buildx) and Python 3.9 or later; nothing else.
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WFD = ROOT / "upstream" / "wfd"
APIS = ROOT / "apis"

# WFD names a few APIs differently in its README (by source folder) and in its compose files.
README_FOLDER_TO_NAME = {
    "cwa-verification-server": "cwa-verification",
    "ncs": "rest-ncs",
    "news": "rest-news",
    "scs": "rest-scs",
}

# Where to ask whether an API is up, for the APIs whose document WFD does not fetch over HTTP.
# A path answering 2XX means ready.
READY_OVERRIDES = {
    "kafka-rest": "/v3/clusters",
    "traccar": "/api/server",
    "cwa-verification": "/version/v1/",
}

SUT_PORT = 8080
JACOCO_PORT = 6300


def run(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout


def wfd_commit():
    return run("git", "rev-parse", "HEAD", cwd=WFD).strip()


def readme_entries():
    """Name, licence, source folder and upstream repository of every REST API in WFD's README."""
    text = (WFD / "README.md").read_text(encoding="utf-8")
    rest = text.split("### REST", 1)[1].split("### GraphQL", 1)[0]
    entries = {}
    pattern = re.compile(r"^\* \*\*(?P<title>.+?)\*\*,? *(?:\((?P<licence>[^)]*)\))?,? *"
                         r"\[(?P<path>[^\]]+)\]\([^)]*\)(?P<rest>.*)$")
    for line in rest.splitlines():
        m = pattern.match(line.strip())
        if not m:
            continue
        folder = m.group("path").rstrip("/").split("/")[-1]
        name = README_FOLDER_TO_NAME.get(folder, folder)
        upstream = re.search(r"from \[(https?://[^\]]+)\]", m.group("rest"))
        licence = m.group("licence") or ""
        if not licence:
            inline = re.search(r"\(([^)]*license[^)]*)\)", m.group("rest"))
            licence = inline.group(1) if inline else "not-known license"
        licence = licence.split(",")[0].strip()
        entries[name] = {
            "title": m.group("title"),
            "license": licence,
            "path": m.group("path"),
            "repository": upstream.group(1) if upstream else None,
        }
    return entries


def docs_urls():
    """The address WFD fetches each API's document from, by API name."""
    import csv
    urls = {}
    with open(WFD / "scripts" / "dockerize" / "data" / "sut.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            urls[row["NAME"]] = row["SWAGGER_URL"].strip()
    return urls


def base_path(document):
    """The path of the first address the document declares: where its operations live."""
    from urllib.parse import urlparse
    text = document.read_text(encoding="utf-8")
    if document.suffix == ".json":
        data = json.loads(text)
        servers = [s.get("url", "") for s in data.get("servers", [])]
        first = servers[0] if servers else (data.get("basePath") or "")
    else:
        found = re.search(r"^servers:\s*\n\s*-\s*url:\s*(.+)$", text, re.M) \
            or re.search(r"^basePath:\s*(.+)$", text, re.M)
        first = found.group(1).strip().strip("'\"") if found else ""
    first = re.sub(r"\{[^}]*\}", "x", first)
    path = first if first.startswith("/") else urlparse(first if "//" in first else "//" + first).path
    return path.rstrip("/")


def served_path(url):
    """The path part of http://localhost:8080/<path>, or None when the document is not served."""
    m = re.match(r"https?:/+localhost:\d+(/.*)$", url or "")
    return m.group(1) if m else None


def auth_for_restest(text):
    """What RESTest's --auth can be given from a Web Fuzzing Commons auth file.

    RESTest takes fixed keys and tokens, so the first user's fixed headers are handed over as they
    are. A user who must log in first cannot be: RESTest does not log in by itself.
    """
    first_user = re.search(r"^( *)- name:", text, flags=re.M)
    indent = first_user.group(1) if first_user else ""
    users = re.split(rf"^{indent}- name:", text, flags=re.M)[1:]
    if not users:
        return {"file": "auth.yaml", "user": None, "restest": [], "login": False}
    first = users[0]
    user = first.splitlines()[0].strip()
    login = bool(re.search(r"loginEndpoint", text, re.I))
    headers = []
    block = re.search(r"fixedHeaders:\s*\n((?:\s+-?\s*(?:name|value):.*\n?)+)", first)
    if block and not login:
        pairs = re.findall(r"name:\s*(.+)\n\s*value:\s*(.+)", block.group(1))
        for header, value in pairs:
            header, value = header.strip().strip("'\""), value.strip().strip("'\"")
            if header.lower() == "cookie" and "=" in value:
                cookie, _, cookie_value = value.partition("=")
                headers.append(f"cookie:{cookie}={cookie_value}")
            else:
                headers.append(f"header:{header}={value}")
    return {"file": "auth.yaml", "user": user, "restest": headers, "login": login}


_digests = {}


def pin(image):
    """The image reference with the digest of what the tag points at today, and its platforms."""
    if "@sha256:" in image:
        return image, None
    if image not in _digests:
        _digests[image] = from_docker_hub(image) or from_registry(image)
    return _digests[image]


def from_docker_hub(image):
    """Asks Docker Hub's web API, which the anonymous pull limit does not count."""
    import urllib.request
    reference, _, tag = image.rpartition(":")
    if not reference or "/" in tag:
        reference, tag = image, "latest"
    parts = reference.split("/")
    if len(parts) > 2 or (len(parts) == 2 and "." in parts[0]):
        return None
    namespace, repository = (parts if len(parts) == 2 else ["library", parts[0]])
    url = f"https://hub.docker.com/v2/namespaces/{namespace}/repositories/{repository}/tags/{tag}"
    try:
        with urllib.request.urlopen(url, timeout=30) as reply:
            data = json.load(reply)
    except OSError as error:
        raise subprocess.CalledProcessError(1, ["docker-hub", "tag", image], stderr=str(error))
    platforms = sorted({f"{i['os']}/{i['architecture']}" for i in data.get("images", [])
                        if i.get("os") not in (None, "unknown")})
    images = [i for i in data.get("images", []) if i.get("digest")]
    # Old multi-platform tags carry no digest of their own; one image alone can be pinned by its own.
    digest = data.get("digest") or (images[0]["digest"] if len(images) == 1 else None)
    if not digest:
        return None
    return f"{image}@{digest}", platforms or None


def from_registry(image):
    manifest = json.loads(run("docker", "buildx", "imagetools", "inspect", image,
                              "--format", "{{json .Manifest}}"))
    platforms = sorted({
        f"{m['platform']['os']}/{m['platform']['architecture']}"
        for m in manifest.get("manifests", [])
        if m.get("platform", {}).get("os") not in (None, "unknown")
    })
    return f"{image}@{manifest['digest']}", platforms or None


def compose_of(name):
    """WFD's compose file for the API, interpolated with its defaults, as a dictionary."""
    source = WFD / "dockerfiles" / f"{name}.yaml"
    out = run("docker", "compose", "-f", str(source), "config", "--format", "json",
              "--no-path-resolution", cwd=source.parent)
    return json.loads(out)


def import_api(name, readme, urls, commit):
    compose = compose_of(name)
    services = compose["services"]
    services.pop("mitmproxy", None)

    sut_name = next(s for s, d in services.items() if d.get("image", "").startswith("webfuzzing/wfd-"))
    # Written beside the API's folder and swapped in at the end, so a failed import keeps the old one.
    final = APIS / name
    target = APIS / f".{name}.importing"
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)

    sut_platforms = None
    for service_name, service in services.items():
        service.pop("networks", None)
        for key in [k for k, v in service.items() if v is None]:
            del service[key]
        deps = service.get("depends_on")
        if isinstance(deps, dict):
            deps.pop("mitmproxy", None)
            for d in deps.values():
                d.pop("required", None)
                if d.get("restart") is False:
                    d.pop("restart")
        image, platforms = pin(service["image"])
        service["image"] = image
        if service_name == sut_name:
            sut_platforms = platforms
            service["ports"] = [f"127.0.0.1::{SUT_PORT}", f"127.0.0.1::{JACOCO_PORT}"]
        else:
            service.pop("ports", None)
        for volume in service.get("volumes", []):
            source = volume.get("source", "")
            if volume.get("type") == "bind" and source.startswith("./"):
                origin = (WFD / "dockerfiles" / source).resolve()
                copy = target / "files" / origin.name
                copy.parent.mkdir(exist_ok=True)
                shutil.copy2(origin, copy)
                volume["source"] = f"./files/{origin.name}"
                volume.pop("bind", None)

    document = None
    for ext in ("json", "yaml"):
        candidate = WFD / "openapi" / f"{name}.{ext}"
        if candidate.exists():
            document = f"openapi.{ext}"
            shutil.copy2(candidate, target / document)
    auth = None
    auth_source = WFD / "auth" / f"{name}-auth.yaml"
    if auth_source.exists():
        shutil.copy2(auth_source, target / "auth.yaml")
        auth = auth_for_restest(auth_source.read_text(encoding="utf-8"))

    entry = readme.get(name, {})
    docs = served_path(urls.get(name))
    dataset = {
        "id": name,
        "title": entry.get("title", name),
        "origin": {
            "dataset": "wfd",
            "repository": "https://github.com/WebFuzzing/Dataset",
            "commit": commit,
            "path": entry.get("path"),
        },
        "upstream": {
            "repository": entry.get("repository"),
            "license": entry.get("license", "not-known license"),
        },
        "language": "jvm",
        "service": sut_name,
        "port": SUT_PORT,
        "document": document,
        "basePath": base_path(target / document) if document else "",
        "documentServedAt": docs,
        "ready": READY_OVERRIDES.get(name, docs),
        "auth": auth,
        "coverage": {"kind": "jacoco-tcpserver", "port": JACOCO_PORT},
        "platforms": sut_platforms,
    }
    out = {"name": f"rd-{name}", "x-dataset": dataset, "services": services}
    for key in ("volumes", "networks"):
        if compose.get(key) and key != "networks":
            out[key] = compose[key]
    header = (f"# {dataset['title']}, imported from the Web Fuzzing Dataset by tools/import-wfd.py.\n"
              f"# Regenerate rather than edit: tools/import-wfd.py {name}\n")
    (target / "compose.yaml").write_text(header + to_yaml(out) + "\n", encoding="utf-8")
    run("docker", "compose", "-f", str(target / "compose.yaml"), "config", "-q")
    shutil.rmtree(final, ignore_errors=True)
    target.rename(final)
    return dataset


# A small YAML writer: compose files hold only maps, lists, strings, numbers, booleans and nulls.

_PLAIN = re.compile(r"^[A-Za-z0-9_./@:+-][A-Za-z0-9_./@:+ =-]*$")
_AMBIGUOUS = re.compile(r"^(true|false|yes|no|on|off|null|~|[-+]?[0-9][0-9_.:eE+-]*)$", re.I)


def scalar(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if _PLAIN.match(text) and not _AMBIGUOUS.match(text) and not text.endswith(":") \
            and ": " not in text and " #" not in text and not text.endswith(" "):
        return text
    return json.dumps(text, ensure_ascii=False)


def to_yaml(value, indent=0):
    pad = "  " * indent
    lines = []
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)) and item:
                lines.append(f"{pad}{scalar(key)}:")
                lines.append(to_yaml(item, indent + 1))
            elif isinstance(item, (dict, list)):
                lines.append(f"{pad}{scalar(key)}: {'{}' if isinstance(item, dict) else '[]'}")
            else:
                lines.append(f"{pad}{scalar(key)}: {scalar(item)}")
    else:
        for item in value:
            if isinstance(item, dict) and item:
                body = to_yaml(item, indent + 1).splitlines()
                lines.append(f"{pad}- {body[0].lstrip()}")
                lines.extend(body[1:])
            elif isinstance(item, list) and item:
                lines.append(f"{pad}-")
                lines.append(to_yaml(item, indent + 1))
            else:
                lines.append(f"{pad}- {scalar(item)}")
    return "\n".join(lines)


def main(names):
    if not (WFD / "dockerfiles").is_dir():
        sys.exit("upstream/wfd is empty: run  git submodule update --init --depth 1 upstream/wfd")
    readme = readme_entries()
    urls = docs_urls()
    commit = wfd_commit()
    available = sorted(p.stem for p in (WFD / "dockerfiles").glob("*.yaml"))
    wanted = names or available
    unknown = [n for n in wanted if n not in available]
    if unknown:
        sys.exit(f"not in WFD: {', '.join(unknown)}")
    skipped = []
    for name in wanted:
        try:
            dataset = import_api(name, readme, urls, commit)
        except subprocess.CalledProcessError as error:
            shutil.rmtree(APIS / f".{name}.importing", ignore_errors=True)
            reason = (error.stderr or "").strip().splitlines()[-1:] or ["failed"]
            skipped.append(name)
            print(f"{name}: NOT IMPORTED: {' '.join(error.cmd[:4])}: {reason[0]}")
            continue
        notes = []
        if not dataset["ready"]:
            notes.append("no readiness path")
        if dataset["platforms"] and "linux/arm64" not in dataset["platforms"]:
            notes.append("amd64 only")
        if not dataset["upstream"]["repository"]:
            notes.append("no upstream repository")
        print(f"{name}: {dataset['title']} ({dataset['upstream']['license']})"
              + (f"  [{'; '.join(notes)}]" if notes else ""))
    if skipped:
        print(f"\n{len(skipped)} not imported: {', '.join(skipped)}")
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
