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
}

# Operations kept out of every run, and why: called with the credentials RESTest was given, each
# leaves the rest of the run unable to test anything. Found by reading stored runs, not guessed.
LEAVE_ALONE = {
    "commafeed": [
        ("POST /rest/admin/user/save", "can change the password of the user RESTest signs in as"),
        ("POST /rest/admin/user/delete", "can delete the user RESTest signs in as"),
        ("POST /rest/user/profile", "changes the password of the user RESTest signs in as"),
        ("POST /rest/user/profile/deleteAccount", "deletes the user RESTest signs in as"),
    ],
    "traccar": [
        ("postServerReboot", "stops the server"),
        ("putUsersId", "can change the password of the user RESTest signs in as"),
        ("deleteUsersId", "can delete the user RESTest signs in as"),
    ],
}

# Credentials files whose users the published image refuses: handing them over would make the run
# worse than giving none, so they are kept, and not handed over.
AUTH_REFUSED = {
    "proxyprint": "the image answers 401 to every user in the file, even on operations open to "
                  "anybody, which answer 200 with no credentials (checked 12 October 2026)",
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


def auth_description(text, auth_server):
    """The x-dataset auth entry: the credentials file, the user ./dataset takes from it (the first),
    and the service that hands out tokens when the login goes to a server other than the API."""
    first_user = re.search(r"^ *- name:\s*(.+)$", text, flags=re.M)
    user = first_user.group(1).strip().strip("'\"") if first_user else None
    server = auth_server if "externalEndpointURL" in text else None
    return {"file": "auth.yaml", "user": user, "server": server}


def operation_names(document):
    """Every operation of the document, each by its operationId and by its method and path."""
    for path, operations in json.loads(document.read_text(encoding="utf-8")).get("paths", {}).items():
        for method, operation in operations.items():
            if method in ("get", "put", "post", "delete", "patch", "head", "options", "trace"):
                yield f"{method.upper()} {path}"
                if operation.get("operationId"):
                    yield operation["operationId"]


def session_enders(document):
    """Operations that end the session a login opened: logging out with the token or cookie RESTest
    was given leaves every later request refused, since RESTest does not log in again."""
    if document.suffix != ".json":
        return []
    found = []
    for path, operations in json.loads(document.read_text(encoding="utf-8")).get("paths", {}).items():
        if not re.search(r"log-?out|sign-?out", path, re.I):
            continue
        for method, operation in operations.items():
            if method in ("get", "put", "post", "delete", "patch", "head", "options"):
                found.append(operation.get("operationId") or f"{method.upper()} {path}")
    return found


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
    # Old tags carry no digest of their own here, and the digests of their images cannot always be
    # pulled: the registry is asked for those.
    digest = data.get("digest")
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
    published = []
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
        # An image built for one processor only is run emulated on the other, rather than refused.
        if platforms and "linux/arm64" not in platforms and "linux/amd64" in platforms \
                and "platform" not in service:
            service["platform"] = "linux/amd64"
        if service_name == sut_name:
            sut_platforms = platforms
            service["ports"] = [f"127.0.0.1::{SUT_PORT}", f"127.0.0.1::{JACOCO_PORT}"]
        else:
            ports = service.pop("ports", None)
            if ports:
                published.append((service_name, int(ports[0]["target"])))
        for volume in service.get("volumes", []):
            source = volume.get("source", "")
            if volume.get("type") == "bind" and not source.startswith("/"):
                origin = (WFD / "dockerfiles" / source).resolve()
                if not origin.exists():
                    raise ValueError(f"{name}: {source} is mounted but not in WFD")
                copy = target / "files" / origin.name
                copy.parent.mkdir(exist_ok=True)
                if origin.is_dir():
                    shutil.copytree(origin, copy)
                else:
                    shutil.copy2(origin, copy)
                # A container runs a mounted script only when it may: WFD's are not marked executable.
                for script in ([copy] if copy.is_file() else copy.rglob("*")):
                    if script.suffix == ".sh":
                        script.chmod(script.stat().st_mode | 0o111)
                volume["source"] = f"./files/{origin.name}"
                volume.pop("bind", None)

    document = None
    for ext in ("json", "yaml"):
        candidate = WFD / "openapi" / f"{name}.{ext}"
        if candidate.exists():
            document = f"openapi.{ext}"
            shutil.copy2(candidate, target / document)
    auth = None
    leave_alone = [{"operation": o, "why": why} for o, why in LEAVE_ALONE.get(name, [])]
    auth_source = WFD / "auth" / f"{name}-auth.yaml"
    if auth_source.exists():
        shutil.copy2(auth_source, target / "auth.yaml")
        text = auth_source.read_text(encoding="utf-8")
        server = None
        if "externalEndpointURL" in text:
            if len(published) != 1:
                raise ValueError(f"{name}: cannot tell which service hands out tokens: {published}")
            server = {"service": published[0][0], "port": published[0][1]}
            services[server["service"]]["ports"] = [f"127.0.0.1::{server['port']}"]
        auth = auth_description(text, server)
        if name in AUTH_REFUSED:
            auth["refused"] = AUTH_REFUSED[name]
        if "loginEndpointAuth" in text and document:
            leave_alone += [{"operation": o, "why": "ends the session the login opened"}
                            for o in session_enders(target / document)]

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
        "leaveAlone": leave_alone,
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
    if leave_alone and document:
        known = set(operation_names(target / document))
        missing = [e["operation"] for e in leave_alone if e["operation"] not in known]
        if missing:
            raise ValueError(f"{name}: no such operations to leave alone: {missing}")
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
