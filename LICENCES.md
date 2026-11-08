# Licences

This repository's own files — the scripts and the documentation — are under the
[Apache License 2.0](LICENSE). Each API's `compose.yaml` is made here by
[`tools/import-wfd.py`](tools/import-wfd.py) from the Web Fuzzing Dataset's compose file for that API.
The APIs themselves are the work of their authors, under their own terms.

This repository holds none of the APIs' application code. Each API's folder holds:

- `compose.yaml`, which tells Docker which images to pull and how to start them: the API's image from
  where the Web Fuzzing Dataset (WFD) publishes it, and its database and other services from their
  own publishers;
- files copied from the [Web Fuzzing Dataset](https://github.com/WebFuzzing/Dataset), byte for byte
  as WFD publishes them at the commit `upstream/wfd` is pinned to: the API's OpenAPI document, its
  credentials file when it has one, and the seed and configuration files its containers mount.

For three APIs, those files include database scripts that are the project's own: arimaa's whole
database (`files/mysql/`: its tables, procedures, triggers, views and data, and its MySQL Workbench
model), blogapi's `blogapi.sql` and testing-system's `01_create_tables.sql`.

WFD says that the code new to it is under the Apache License 2.0, and that the sources it took from
each project keep that project's own licence. The table gives, for every API, the licence the dataset
records (WFD's, unless the project's repository states another), what the project's repository says
today, and what is copied here.

## APIs without a licence that can be checked

Sixteen APIs have none:

- fourteen projects publish no licence in their repository: adoptme, arimaa, digitalbanking,
  erc20-rest-service, gdpr-kv, gestaohospital, joinus, lovemining, redis-sample, reservations-api,
  spring-actuator-demo, spring-ecommerce, tracking-system and youtube-mock;
- rest-ncs and rest-scs are artificial examples written by WFD's authors, who say that the code new to
  WFD is under the Apache License 2.0 and list both as "not-known license".

They are kept. What this repository copies of each is listed below, and is identical to what WFD
publishes. scout-api's repository is no longer on GitHub; an archived copy of it holds the MIT licence
WFD records.

**If you are an author of an API here** and do not want it in this dataset, open an issue in this
repository, and it is removed from the dataset.

## Every API

Checked against each project's repository on 8 November 2026. `./dataset list` shows the licence the
dataset records, and `LICENCES` in [`tools/import-wfd.py`](tools/import-wfd.py) holds the corrections
made to WFD's. An API added to the dataset gets its row here.

| API | Licence | The project's repository, 8 November 2026 | Copied from WFD |
|---|---|---|---|
| [`adoptme`](apis/adoptme/compose.yaml) | not-known license | [none published](https://github.com/daanimelian/Programacion3-TPO) | `openapi.json` |
| [`arimaa`](apis/arimaa/compose.yaml) | not-known license | [none published](https://github.com/KEAArimaaProject/arimaa-backend) | `auth.yaml`, `files/` (13 files), `openapi.json`; `files/mysql/` is the project's own database: its tables, procedures, triggers, views and data, and its MySQL Workbench model |
| [`bibliothek`](apis/bibliothek/compose.yaml) | MIT | [MIT](https://github.com/PaperMC/bibliothek) | `openapi.json` |
| [`blogapi`](apis/blogapi/compose.yaml) | AGPL | [AGPL-3.0](https://github.com/osopromadze/Spring-Boot-Blog-REST-API) | `auth.yaml`, `files/` (2 files), `openapi.json`; `blogapi.sql` is the project's own |
| [`catwatch`](apis/catwatch/compose.yaml) | Apache | [Apache-2.0](https://github.com/zalando-incubator/catwatch) | `openapi.json` |
| [`commafeed`](apis/commafeed/compose.yaml) | Apache | [Apache-2.0](https://github.com/Athou/commafeed) | `auth.yaml`, `openapi.json` |
| [`cwa-verification`](apis/cwa-verification/compose.yaml) | Apache | [Apache-2.0](https://github.com/corona-warn-app/cwa-verification-server) | `openapi.json` |
| [`digitalbanking`](apis/digitalbanking/compose.yaml) | not-known license | [none published](https://github.com/jphaugla/Redisearch-Digital-Banking-redisTemplate) | `openapi.json` |
| [`erc20-rest-service`](apis/erc20-rest-service/compose.yaml) | not-known license | [none published](https://github.com/web3labs/erc20-rest-service) | `openapi.json` |
| [`familie-ba-sak`](apis/familie-ba-sak/compose.yaml) | MIT | [MIT](https://github.com/navikt/familie-ba-sak) | `auth.yaml`, `files/` (1 file), `openapi.json` |
| [`features-service`](apis/features-service/compose.yaml) | Apache | [Apache-2.0](https://github.com/JavierMF/features-service) | `openapi.json` |
| [`gdpr-kv`](apis/gdpr-kv/compose.yaml) | not-known license | [none published](https://github.com/jessicant/GDPR-KV) | `files/` (1 file), `openapi.json` |
| [`genome-nexus`](apis/genome-nexus/compose.yaml) | MIT | [MIT](https://github.com/genome-nexus/genome-nexus) | `openapi.json` |
| [`gestaohospital`](apis/gestaohospital/compose.yaml) | not-known license | [none published](https://github.com/ValchanOficial/GestaoHospital) | `openapi.json` |
| [`http-patch-spring`](apis/http-patch-spring/compose.yaml) | MIT | [MIT](https://github.com/cassiomolin/http-patch-spring) | `openapi.json` |
| [`jasper`](apis/jasper/compose.yaml) | MIT | [MIT](https://github.com/cjmalloy/jasper) | `auth.yaml`, `openapi.json` |
| [`joinus`](apis/joinus/compose.yaml) | not-known license | [none published](https://github.com/KLAJDI16/joinUs) | `auth.yaml`, `files/` (2 files), `openapi.json` |
| [`kafka-rest`](apis/kafka-rest/compose.yaml) | Confluent Community License | [Confluent Community License 1.0](https://github.com/confluentinc/kafka-rest) | `openapi.json` |
| [`komga`](apis/komga/compose.yaml) | MIT | [MIT](https://github.com/gotson/komga) | `auth.yaml`, `openapi.json` |
| [`languagetool`](apis/languagetool/compose.yaml) | LGPL | [LGPL-2.1](https://github.com/languagetool-org/languagetool) | `openapi.json` |
| [`lovemining`](apis/lovemining/compose.yaml) | not-known license | [none published](https://github.com/Andryd22/LoveMining) | `auth.yaml`, `files/` (2 files), `openapi.json` |
| [`management-cassandra`](apis/management-cassandra/compose.yaml) | Apache | [Apache-2.0](https://github.com/k8ssandra/management-api-for-apache-cassandra) | `files/` (1 file), `openapi.json` |
| [`market`](apis/market/compose.yaml) | MIT | [MIT](https://github.com/aleksey-lukyanets/market) | `auth.yaml`, `openapi.json` |
| [`microcks`](apis/microcks/compose.yaml) | Apache | [Apache-2.0](https://github.com/microcks/microcks) | `auth.yaml`, `files/` (1 file), `openapi.json` |
| [`movies-xml`](apis/movies-xml/compose.yaml) | LGPL | [LGPL-3.0](https://github.com/suarezrominajulieta/movies-xml) | `openapi.json` |
| [`ocvn`](apis/ocvn/compose.yaml) | MIT | [MIT](https://github.com/devgateway/ocvn) | `auth.yaml`, `openapi.json` |
| [`ohsome-api`](apis/ohsome-api/compose.yaml) | AGPL-3.0 | [AGPL-3.0](https://github.com/GIScience/ohsome-api) | `openapi.json` |
| [`pay-publicapi`](apis/pay-publicapi/compose.yaml) | MIT | [MIT](https://github.com/alphagov/pay-publicapi) | `auth.yaml`, `openapi.json` |
| [`person-controller`](apis/person-controller/compose.yaml) | Apache | [Apache-2.0](https://github.com/mongodb-developer/java-spring-boot-mongodb-starter) | `openapi.json` |
| [`petclinic-rest`](apis/petclinic-rest/compose.yaml) | Apache | [Apache-2.0](https://github.com/spring-petclinic/spring-petclinic-rest) | `openapi.json` |
| [`proxyprint`](apis/proxyprint/compose.yaml) | Apache | [Apache-2.0](https://github.com/ProxyPrint/proxyprint-kitchen) | `auth.yaml`, `openapi.json` |
| [`quartz-manager`](apis/quartz-manager/compose.yaml) | Apache | [Apache-2.0](https://github.com/fabioformosa/quartz-manager) | `auth.yaml`, `openapi.json` |
| [`redis-sample`](apis/redis-sample/compose.yaml) | not-known license | [none published](https://github.com/hendisantika/spring-boot-redis-sample) | `openapi.json` |
| [`reservations-api`](apis/reservations-api/compose.yaml) | not-known license | [none published](https://github.com/cyrilgavala/reservations-api) | `auth.yaml`, `files/` (3 files), `openapi.json` |
| [`rest-ncs`](apis/rest-ncs/compose.yaml) | not-known license | none: WFD's own artificial example | `openapi.json` |
| [`rest-news`](apis/rest-news/compose.yaml) | LGPL | [LGPL-3.0](https://github.com/arcuri82/testing_security_development_enterprise_systems) | `openapi.json` |
| [`rest-scs`](apis/rest-scs/compose.yaml) | not-known license | none: WFD's own artificial example | `openapi.json` |
| [`restcountries`](apis/restcountries/compose.yaml) | MPL | [MPL-2.0](https://github.com/apilayer/restcountries) | `openapi.yaml` |
| [`scout-api`](apis/scout-api/compose.yaml) | MIT | no longer on GitHub; an [archived copy](https://archive.softwareheritage.org/swh:1:rev:841fc61c09e9006a267fa04d8e4151ea956aaacb) holds an MIT licence | `auth.yaml`, `openapi.json` |
| [`session-service`](apis/session-service/compose.yaml) | Apache-2.0 | [Apache-2.0](https://github.com/cBioPortal/session-service) | `openapi.json` |
| [`spring-actuator-demo`](apis/spring-actuator-demo/compose.yaml) | not-known license | [none published](https://github.com/callicoder/spring-boot-actuator-demo) | `auth.yaml`, `openapi.json` |
| [`spring-batch-rest`](apis/spring-batch-rest/compose.yaml) | Apache | [Apache-2.0](https://github.com/chrisgleissner/spring-batch-rest) | `openapi.json` |
| [`spring-ecommerce`](apis/spring-ecommerce/compose.yaml) | not-known license | [none published](https://github.com/SaiUpadhyayula/SpringAngularEcommerce) | `auth.yaml`, `files/` (2 files), `openapi.json` |
| [`spring-rest-example`](apis/spring-rest-example/compose.yaml) | MIT | [MIT](https://github.com/phantasmicmeans/spring-boot-restful-api-example) | `openapi.json` |
| [`swagger-petstore`](apis/swagger-petstore/compose.yaml) | Apache | [Apache-2.0](https://github.com/swagger-api/swagger-petstore) | `openapi.json` |
| [`testing-system`](apis/testing-system/compose.yaml) | MIT | [MIT](https://github.com/mirodilkamilov/testing-system) | `auth.yaml`, `files/` (2 files), `openapi.json`; `01_create_tables.sql` is the project's own |
| [`tiltaksgjennomforing`](apis/tiltaksgjennomforing/compose.yaml) | MIT | [MIT](https://github.com/navikt/tiltaksgjennomforing-api) | `auth.yaml`, `files/` (1 file), `openapi.json` |
| [`traccar`](apis/traccar/compose.yaml) | Apache | [Apache-2.0](https://github.com/traccar/traccar) | `auth.yaml`, `openapi.json` |
| [`tracking-system`](apis/tracking-system/compose.yaml) | not-known license | [none published](https://github.com/SelimHorri/project-tracking-system-backend-app) | `auth.yaml`, `openapi.json` |
| [`user-management`](apis/user-management/compose.yaml) | MIT | [MIT](https://github.com/andreagiassi/microservice-rbac-user-management) | `openapi.json` |
| [`webgoat`](apis/webgoat/compose.yaml) | GPL | [GPL-2.0-or-later](https://github.com/WebGoat/WebGoat) | `auth.yaml`, `openapi.json` |
| [`youtube-mock`](apis/youtube-mock/compose.yaml) | not-known license | [none published](https://github.com/opensourcingapis/YouTubeMock) | `openapi.yaml` |
