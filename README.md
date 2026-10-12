# RESTest dataset

Open-source REST APIs that run on one machine with Docker, for testing
[RESTest](https://github.com/isa-group/RESTest): checking a change or a release on real APIs,
comparing two versions of the tool, and, later, showing what it finds on the project's website.

Each API is a folder that starts on its own — no build, no account, nothing to install but Docker —
with the OpenAPI document RESTest is given, pinned images so that the API under test is the same
next month, and the credentials it needs when it has any. A small script starts an API, waits until
it answers, runs RESTest against it, and removes it again so that every run starts from scratch.

The first 52 APIs come from the [Web Fuzzing Dataset](#acknowledgements). More will be added as they
are found, from other collections and from open-source projects directly.

## Quick start

Docker with Compose v2 and Python 3.9 or later; nothing else. RESTest is whatever command runs it —
a checkout's `./restest`, a release's `bin/restest`.

```bash
git clone https://github.com/isa-group/restest-dataset
cd restest-dataset

./dataset list                                    # what is there
./dataset up petclinic-rest                       # start one; prints its address when it answers
./dataset down petclinic-rest                     # stop it and throw its data away

./dataset run suite:smoke --restest ~/Repositories/RESTest/restest --budget 60s
./dataset run petclinic-rest kafka-rest --restest ~/Repositories/RESTest/restest \
    --budget 5m --runs 5 --out out/before-the-change
./dataset summary out/before-the-change           # one line per run, and summary.csv
```

`run` takes API names and suites (`suite:<name>`, a file in `suites/`; `suite:all` is every API).
Each run of each API goes into `<out>/<api>/run-<n>/`: RESTest's `report.json` and screen output,
its exit code, the API's own log, and `credentials.txt`, which says how RESTest was let in (never
the values). An API that does not start is noted in `start-failed.txt` and the campaign goes on. `campaign.json` records the command, the budget and the
dataset commit. Anything after `--` is handed to `restest run` as it is:

```bash
./dataset run suite:smoke --restest ~/Repositories/RESTest/restest -- --store --seed 42
```

The images are pulled from Docker Hub the first time an API starts. Docker Hub allows few
anonymous pulls an hour, so `docker login` before starting many APIs for the first time.

## What is in an API's folder

```
apis/<api>/
  compose.yaml   the API and what it needs (a database, a broker…), every image pinned by digest,
                 with the dataset's description of the API under the key x-dataset
  openapi.json   the document RESTest is given (or openapi.yaml)
  auth.yaml      credentials, in Web Fuzzing Commons format, when the API has any
  files/         seed data and configuration the compose file mounts
  setup          optional: run once the API answers; prints values for RESTest's --auth
```

The API is published on an ephemeral port of `127.0.0.1` only — several of these applications are
deliberately vulnerable and must not be reachable from the network — so several APIs, or several
copies of one, can run side by side.

`x-dataset` describes the API:

| Key | What it says |
|---|---|
| `id`, `title` | The folder's name, and the API's |
| `origin` | Where the entry comes from: `dataset` (`wfd`, or `own` for one written here), its repository, the commit and the path in it |
| `upstream` | The project the API is, and its licence |
| `service`, `port` | The compose service that is the API, and the port it listens on inside its container |
| `document` | The file in the folder RESTest is given |
| `basePath` | The path of the first address the document declares, where its operations live. It is handed to RESTest as part of `--url`, so that which address RESTest picks from the document never decides where the requests go |
| `documentServedAt` | Where the running API serves its own document, when it does |
| `ready` | A path that answers 2XX once the API is ready. When it is null, any answer but 502 or 503 means ready |
| `auth` | The credentials file, the user taken from it (the first, unless another is named), and, when the login goes to a server of its own rather than to the API, which compose service that is and its port. `leaveAlone` names the operations that would end a session a login opened, such as `logout` |
| `coverage` | How code coverage can be read: the WFD images run a JaCoCo agent as a TCP server on port 6300, published beside the API |
| `platforms` | The processors the API's image is published for |

## Credentials

`./dataset run` hands RESTest the API's credentials, when it has any, as a user of RESTest would:

- **Fixed** — a key, a token or a Basic header that never changes: given to `--auth` as it is.
- **Login** — the API wants a user and a password first. Once the API answers, `./dataset` logs in
  as the credentials file says — the request, its body, and where the token is in the reply or that
  the reply sets a session cookie — and gives RESTest the token or the cookies. RESTest itself
  does not log in.
- **Login at a server of its own** — a stand-in OAuth server or Keycloak inside the compose file.
  That server is published on `127.0.0.1` too, and the login is sent to it as the API would reach
  it, so the token names the issuer the API expects.

A login is retried for up to three minutes while the server that answers it is still starting. One
that fails is written in `credentials.txt` and on the screen, and that run goes on without
credentials.

A session can be ended by the API itself: RESTest calls `logout` like any other operation, and every
request after it is refused, since RESTest does not log in again. So when a login opened the
session, the operations in `leaveAlone` are kept out of the run, through a plan that is RESTest's
own with `operations.only` added (`plan.yaml` in the run's folder). The importer fills `leaveAlone`
with the operations whose path says log out or sign out. A plan given after `--` takes precedence,
and `credentials.txt` then says the session was not protected. RESTest is given one user and does not renew a token, so a token that expires during a
long run leaves the rest of it refused.

`--no-auth` gives RESTest the document and nothing else. That is RESTest's design target — an
unknown API, and only its document — and the way to measure what RESTest does on its own.
`./dataset up <api>` prints the `--auth` options for a run by hand.

## Suites

A suite is a text file in `suites/`, one API per line, `#` for comments.

| Suite | What it is for |
|---|---|
| `smoke` | Two small APIs that start in seconds: does everything work at all |
| `all` | Every API (built in, no file) |

## Adding an API

**From the Web Fuzzing Dataset.** `upstream/wfd` is that dataset, as a git submodule pinned to a
commit. It is not needed to run anything here, only to import:

```bash
git submodule update --init --depth 1 upstream/wfd
tools/import-wfd.py                      # every API it packages, or name some
```

The importer takes WFD's compose file without its recording proxy, pins every image to the digest
its tag points at today, publishes the API on `127.0.0.1`, and copies the API's document,
credentials and seed files. To move to a newer WFD, move the submodule and import again; the diff
shows what changed. Two APIs WFD lists are not imported yet because their images are not published:
`flight-search-api` and `notebook-manager`.

**From anywhere else.** Write `apis/<api>/compose.yaml` by hand, with `x-dataset.origin.dataset:
own`, pin its images by digest (`docker buildx imagetools inspect <image>:<tag>` prints the digest),
commit a copy of the API's document, and add a `setup` script if the API needs an account or a token
before it can be tested. `setup` gets `DATASET_URL`, `DATASET_COMPOSE` and `DATASET_SERVICE`, and
prints one `--auth` value a line. Then `./dataset run <api> --restest … --budget 30s` to see that
it starts and that RESTest gets past the door, and regenerate the catalogue:

```bash
{ printf '# Catalogue\n\nEvery API in the dataset, written by `./dataset list --markdown`. Do not edit by hand.\n\n'; ./dataset list --markdown; } > CATALOGUE.md
```

The [catalogue](CATALOGUE.md) lists every API with its licence and where it comes from.

## Acknowledgements

Most of this dataset is the **Web Fuzzing Dataset (WFD)**, formerly EMB, built and maintained by
Andrea Arcuri, Man Zhang, Omur Sahin and the other EvoMaster contributors:
<https://github.com/WebFuzzing/Dataset>. They chose the applications, made them run in containers,
wrote their seed data and credentials, and publish the images every API here starts from. This
repository adds a way to run them with RESTest and nothing else; the work of collecting them is
theirs. Please cite them when you use these APIs:

> O. Sahin, M. Zhang, A. Arcuri.
> **WFC/WFD: Web Fuzzing Commons, Dataset and Guidelines to Support Experimentation in REST API
> Fuzzing**. [arXiv:2509.01612](https://arxiv.org/abs/2509.01612)

> A. Arcuri, M. Zhang, A. Golmohammadi, A. Belhadi, J. P. Galeotti, B. Marculescu, S. Seran.
> **EMB: A Curated Corpus of Web/Enterprise Applications and Library Support for Software Testing
> Research**. In *IEEE International Conference on Software Testing, Verification and Validation
> (ICST)*, 2023.

## Licence

This repository's own files — the scripts, the compose files written here, the documentation — are
under the [Apache License 2.0](LICENSE). The APIs are not: each is the work of its authors under its
own licence, named in its entry and in the [catalogue](CATALOGUE.md), and several are marked
"not-known license" by WFD. This repository does not contain their source code; their images are
pulled from where their publishers put them. The documents, credentials and seed files copied from
WFD are WFD's, under its licence. Check an API's licence before redistributing anything of it, and
before this repository is made public.
