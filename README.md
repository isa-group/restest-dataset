# RESTest dataset

The 52 REST APIs in this repository are taken from the
[Web Fuzzing Dataset](https://github.com/WebFuzzing/Dataset) (WFD). Choosing the applications, making
them run in containers, gathering their seed data, writing their credentials and publishing their
images is the work of WFD's maintainers, and the credit for it is theirs alone. Please cite them when
you use these APIs: the [acknowledgements](#acknowledgements) say how.

This repository only packages their APIs so that [RESTest](https://github.com/isa-group/RESTest) can
be evaluated on them regularly: to check a change or a release on real APIs, to compare two versions
of the tool, and to run the campaign of each released version whose results RESTest's website shows.

Each API is a folder that starts on its own — no build, no account, nothing to install but Docker —
with the OpenAPI document RESTest is given, pinned images so that the API under test is the same
next month, and the credentials it needs when it has any. A small script starts an API, waits until
it answers, runs RESTest against it, and removes it again so that every run starts from scratch.

## Quick start

Docker with Compose v2 and Python 3.9 or later; nothing else. RESTest is whatever command runs it —
a checkout's `./restest`, a release's `bin/restest`; the examples use a built checkout of RESTest
beside this one, `../RESTest/restest`.

```bash
git clone https://github.com/isa-group/restest-dataset
cd restest-dataset

./dataset list                                    # what is there
./dataset up petclinic-rest                       # start one; prints its address when it answers
./dataset down petclinic-rest                     # stop it and throw its data away

./dataset run suite:smoke --restest ../RESTest/restest --budget 60s
./dataset run petclinic-rest kafka-rest --restest ../RESTest/restest \
    --budget 5m --runs 5 --out out/before-the-change
./dataset summary out/before-the-change           # one line per run, and summary.csv
```

`run` takes API names and suites (`suite:<name>`, a file in `suites/`; `suite:all` is every API).
Each run of each API goes into `<out>/<api>/run-<n>/`: RESTest's `report.json` and screen output,
its exit code, the API's own log, and `credentials.txt`, which says how RESTest was let in (never
the values). An API that does not start is noted in `start-failed.txt` and the campaign goes on. `campaign.json` records the command, the budget and the
dataset commit. Anything after `--` is handed to `restest run` as it is:

```bash
./dataset run suite:smoke --restest ../RESTest/restest -- --store --seed 42
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
| `ready` | A path that answers once the API is ready: 2XX, or 401 or 403 when the API keeps it for signed-in users. When it is null, any answer but 502 or 503 means ready |
| `auth` | The credentials file, the user taken from it (the first, unless another is named), and, when the login goes to a server of its own rather than to the API, which compose service that is and its port. `refused` says why the credentials are not handed over, when the API turns them down |
| `leaveAlone` | Operations kept out of every run, each with why: called with the credentials RESTest holds, each leaves the rest of the run unable to test anything |
| `coverage` | How code coverage can be read: the WFD images run a JaCoCo agent as a TCP server on port 6300, published beside the API |
| `platforms` | The processors the API's image is published for. An image published for `linux/amd64` alone is run emulated on Apple silicon |

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
credentials. RESTest is given one user and does not renew a token, so a token that expires during a
long run leaves the rest of it refused.

`--no-auth` gives RESTest the document and no credentials. That is RESTest's design target — an
unknown API, and only its document — and the way to measure what RESTest does on its own.
`./dataset up <api>` prints the `--auth` options for a run by hand.

## Operations left alone

RESTest calls every operation it can, with the credentials it holds, and some operations take
those credentials away: a `logout` ends the session a login opened, a password change or a deleted
account leaves the key refused, a reboot stops the server. Every request after that is refused or
unanswered, and the rest of the run tests nothing. Three such cases are known:

| API | What RESTest did |
|---|---|
| testing-system, joinus | called `logout` with the session it was given |
| commafeed | saved the user it signed in as, with a new password, by the id an earlier reply showed it |
| traccar | called `POST /server/reboot` |

So the operations in `leaveAlone` are kept out of every run, through a plan that is RESTest's own
with `operations.only` added (`plan.yaml` in the run's folder; `left-alone.txt` says which, and
why). The importer puts there the operations whose path says log out or sign out when the API's
credentials need a login, and the ones listed in `LEAVE_ALONE` in `tools/import-wfd.py`, found by
reading stored runs. `--all-operations` lets RESTest call them. A plan given after `--` takes
precedence, and `left-alone.txt` then says nothing was left alone.

## What this repository holds

The dataset and the scripts that run it, nothing else. What a run produces — reports, logs, stored
requests — goes into `out/` unless `--out` says otherwise, and `out/` is ignored by git: results
are never committed here. The showcase's campaigns are kept as assets of this repository's releases,
also never as commits.

## Suites

A suite is a text file in `suites/`, one API per line, `#` for comments.

| Suite | What it is for |
|---|---|
| `smoke` | Two small APIs that start in seconds: does everything work at all |
| `all` | Every API (built in, no file) |

## The showcase

What RESTest finds on these APIs is shown on its website, one campaign for each released version. A
campaign is the workflow [`showcase.yml`](.github/workflows/showcase.yml): it runs a released RESTest
against every API, each started from scratch in a job of its own on GitHub's runners, and ends in a
draft release of this repository, `showcase-v<version>`. Someone who can write here launches it from
`main` once the version is published:

```bash
gh workflow run showcase.yml -f version=2.5.0 -f budget=15m
gh run watch
```

`budget` is how long RESTest tests each API, at most `5h`. `seed` can be given too; left out, one is
chosen and every API is tested with it. Each job downloads RESTest's archive from its release and
checks it against the release's checksums, pulls the API's images, and runs `./dataset run <api>`,
with the API's credentials and its operations left alone, as on a laptop.

What bounds a campaign is GitHub's:

- A job is stopped after six hours, with nothing kept. The step that runs RESTest is given the budget
  and half an hour more, to start the API, log in and write the reports, so the budget is at most five
  hours.
- GitHub's free plan runs 20 jobs at once across the whole organisation. Ten APIs are tested at a time,
  and the other ten places are left to the builds of the organisation's other repositories.
- A public repository's runners have 4 CPUs and 16 GB of memory. The manifest says what the campaign's
  first job had, and how much disk it had left.
- Some APIs write a hundred megabytes of log a minute while they are tested. Each container's log is
  kept under 200 MB, so that the runner's disk does not fill.

The draft holds `manifest.json`, and `<api>.report.json` and `<api>.report.html` for each API that
has a report. Only those who can write here see it, until someone has looked at it and published it:

```bash
gh release edit showcase-v2.5.0 --draft=false
```

A second campaign of a version stops at its first step while a release of it exists, draft or
published: a published campaign is never replaced.

**When a job fails.** The release is drafted whatever became of each API, and the manifest says
what that was. A job goes red when something kept RESTest from testing its API: its images could not
be pulled after three tries, RESTest ended without a report or ran out of time, or a step before it
failed, such as downloading the archive or logging in to Docker Hub. An API that does not answer in
time leaves its job green: that is what the API did. To try the red ones again with the same seed,
delete the draft (`gh release delete showcase-v2.5.0`) and choose "Re-run failed jobs" on the run:
the other APIs' results are kept, and the draft is made again. To try a green one again, delete the
draft and choose "Re-run this job" on that API's job. A report written by another version than the
campaign's stops its job and the draft, since it means the wrong archive was tested.

**What a run keeps besides the release.** For 30 days, each job keeps, as an artifact of the run:
its entry for the manifest, both reports, RESTest's screen output and the last 2,000 lines of the
API's own log. None of it is secret. The credentials are those of this repository's `auth.yaml`
files, or come from logging in to containers thrown away with the job. RESTest's reports show a
key it was handed as a mask. `credentials.txt` never holds values.

**Docker Hub.** The images are pulled without an account. If Docker Hub's limit on such pulls gets in
the way, give the repository the secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`, a read-only
access token: each job then logs in to pull its API's images, and logs out before the API starts, so
that the token is in no file while the API and RESTest run.

**The manifest** is what the website reads:

| Key | What it says |
|---|---|
| `format` | `1`. It goes up when a key changes its meaning or goes away; a new key leaves it as it is |
| `restest` | The version, its archive and the archive's SHA-256 |
| `budget` | Each API's, written as `report.json` writes lengths of time: `PT15M` |
| `seed` | As text, because a seed can have more digits than a JSON reader keeps exactly |
| `runner` | The first job's machine: its label, image, CPUs, memory and free disk in GiB once its API was done, and the Java RESTest ran on |
| `startedAt`, `finishedAt` | When the campaign started, and when its manifest was written |
| `dataset` | This repository, and the commit the campaign ran |
| `workflowRun` | The run, with each job's log and artifact |
| `apis` | One entry for each API, in the order `./dataset list` gives |

and each entry of `apis`:

| Key | What it says |
|---|---|
| `id`, `title`, `license`, `upstream` | From the API's `x-dataset` |
| `outcome` | `ran`; `apiDidNotStart`, the API did not answer in time; `imagesNotPulled`, its images could not be pulled; `noReport`, RESTest left no report, or one that cannot be read |
| `reason` | Why, in one line, when it did not run |
| `exitCode` | RESTest's exit code, when it ended |
| `credentials`, `leftAlone` | The line of `credentials.txt` and of `left-alone.txt`, as it is |
| `startedAt`, `finishedAt` | When its job started and ended |
| `report`, `page` | The names of its `report.json` and `report.html` in the release, or `null` |

There are no figures in the manifest: each `report.json` holds them.

**Running an API as a campaign did.** Anyone can repeat an API of a campaign on their own machine,
with that version's archive from RESTest's releases and the manifest's budget and seed:

```bash
./dataset run petclinic-rest --restest restest-2.5.0/bin/restest --budget 15m -- --seed 12345
```

The run will be similar rather than the same: what RESTest sends depends on what the API answers,
and the machine is another.

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

The [catalogue](CATALOGUE.md) lists every API with its licence and where it comes from. Give the
API its row in [LICENCES.md](LICENCES.md) too: its licence, what its repository says, and what is
copied here.

## Acknowledgements

Most of this dataset is the **Web Fuzzing Dataset (WFD)**, formerly EMB, built and maintained by
Andrea Arcuri, Man Zhang, Omur Sahin and the other EvoMaster contributors:
<https://github.com/WebFuzzing/Dataset>. They chose the applications, made them run in containers,
gathered their seed data, wrote their credentials, and publish the images every API here starts
from. This
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

This repository's own files — the scripts and the documentation — are under the
[Apache License 2.0](LICENSE); each `compose.yaml` is made here from WFD's. The APIs are the work of
their authors, under their own terms. This repository holds none of their application code: their
images are pulled from where their publishers put them, and the documents, credentials and seed
files here are copied from WFD as WFD publishes them, which for three APIs include the project's own
database scripts. [LICENCES.md](LICENCES.md) gives, for every API, its licence, what its repository
says and what is copied here; sixteen have no licence that can be checked. An author who does not
want their API here can open an issue, and it is removed from the dataset.
