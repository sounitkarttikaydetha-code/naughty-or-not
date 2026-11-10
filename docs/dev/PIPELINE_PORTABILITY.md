# Pipeline Portability Guide: GitHub Actions to GitLab CI/CD

> **Clearance Check Canary (v2.0.1)**  
> **Prepared by:** Antigravity (AI assistant) — for review by Sounit Karttikay  
> **Status:** Reference specification for Enterprise DevSecOps migration  
> **Notice:** *Canary build — for evaluation only. Not for screening decisions.*

---

## 1. Executive Summary

This document specifies the exact mapping between the GitHub Actions canary workflow (`.github/workflows/canary.yml`) and GitLab CI/CD (`.gitlab-ci.yml`), which represents the organisation's standard enterprise DevSecOps platform.

When the organisation's Enterprise Architecture (EA) and Cybersecurity teams approve hosting and deploying Clearance Check on internal enterprise infrastructure, the CI/CD pipeline can be transitioned to an on-premise or VPC GitLab instance without code alterations or re-engineering.

> [!IMPORTANT]
> In accordance with non-negotiable project boundaries, **no company data, company credentials, or internal enterprise GitLab resources were accessed or modified** during the creation of this specification. All mappings are defined against generic, standardized GitLab CI/CD schemas (GitLab 16.x+).

---

## 2. Stage Mapping Matrix

The Canary CI workflow is organized into seven distinct stages across the DevSecOps lifecycle:

| GitHub Actions Job | GitLab CI Stage | Purpose & Verification | Failure Action |
|---|---|---|---|
| `signature_integrity` | `.pre` | Hard Rule 9: Verifies author signature SHA-256 hash is 100% unaltered. | **Blocking** |
| `layered_architecture_lint` | `lint` | C1: AST layer verification (domain -> application -> adapters -> interfaces). Zero reverse imports. | **Blocking** |
| `database_migrations` | `test` | C3: Schema migration up/down, append-only triggers, lossless v1 import. | **Blocking** |
| `roles_and_auth` | `test` | C4: RBAC (5 roles: Screener, Reviewer, Compliance, Admin, Auditor) & Four-Eyes rule. | **Blocking** |
| `isolation_verification` | `test` | 1.2: Side-by-side desktop isolation (%LOCALAPPDATA%\ClearanceCheckCanary\). | **Blocking** |
| `api_contract_tests` | `test` | C2: OpenAPI 3.1.0 schema compliance and RFC 7807 problem details. | **Blocking** |
| `results_parity_job` | `parity` | C6: 100% parity against v1.2.1 baseline (60 locked queries, 300 evaluations). | **Blocking** |
| `dependency_and_image_scan` | `security` | GitLab Dependency Scanning & Container Scanning (Trivy / Grype / pip-audit). | **Blocking** on CRITICAL |
| `container_build_and_test` | `package` | C5: Multi-stage non-root container build and health probes. | **Blocking** |
| `canary_release` | `release` | Automated canary pre-release artifact publishing (`v*-canary.*`). | Manual approval |

---

## 3. Complete Reference `.gitlab-ci.yml` Template

The following production-ready `.gitlab-ci.yml` can be placed into the root of the repository when imported into an enterprise GitLab namespace:

```yaml
# ==============================================================================
# CLEARANCE CHECK CANARY — ENTERPRISE GITLAB CI/CD PIPELINE
# ==============================================================================
image: python:3.12-slim-bookworm

stages:
  - .pre
  - lint
  - test
  - parity
  - security
  - package
  - release

variables:
  PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"
  CANARY_ENV: "testing"
  DOCKER_DRIVER: overlay2
  DOCKER_TLS_CERTDIR: "/certs"

cache:
  paths:
    - .cache/pip
    - .venv/

default:
  before_script:
    - python -m venv .venv
    - . .venv/bin/activate
    - pip install --upgrade pip
    - pip install -r requirements.txt
    - pip install pytest fastapi pydantic httpx pyyaml pillow

# ------------------------------------------------------------------------------
# STAGE: .pre — Hard Rule 9 Signature Verification
# ------------------------------------------------------------------------------
verify_signature_hash:
  stage: .pre
  script:
    - python tests/test_signature.py
  rules:
    - if: '$CI_PIPELINE_SOURCE == "push" || $CI_PIPELINE_SOURCE == "merge_request_event"'

# ------------------------------------------------------------------------------
# STAGE: lint — Architectural Boundaries (C1)
# ------------------------------------------------------------------------------
lint_layered_architecture:
  stage: lint
  script:
    - pytest tests/test_layered_architecture.py -v
  rules:
    - if: '$CI_PIPELINE_SOURCE == "push" || $CI_PIPELINE_SOURCE == "merge_request_event"'

# ------------------------------------------------------------------------------
# STAGE: test — Functional, Migrations, Security & Contract
# ------------------------------------------------------------------------------
test_db_migrations:
  stage: test
  script:
    - pytest tests/test_db_migration.py -v

test_rbac_and_four_eyes:
  stage: test
  script:
    - pytest tests/test_roles_and_auth.py -v

test_side_by_side_isolation:
  stage: test
  script:
    - pytest tests/test_side_by_side_isolation.py -v

test_openapi_contracts:
  stage: test
  before_script:
    - . .venv/bin/activate
    - python scripts/init_data.py
  script:
    - pytest tests/test_api_contract.py -v

# ------------------------------------------------------------------------------
# STAGE: parity — v1.2.1 Parity Job (C6)
# ------------------------------------------------------------------------------
results_parity_verification:
  stage: parity
  before_script:
    - . .venv/bin/activate
    - python scripts/init_data.py
  script:
    - pytest tests/test_results_parity.py -v
  artifacts:
    when: always
    reports:
      junit: junit-parity.xml

# ------------------------------------------------------------------------------
# STAGE: security — Dependency & Container Scanning
# ------------------------------------------------------------------------------
dependency_scanning:
  stage: security
  image: python:3.12-slim-bookworm
  before_script:
    - pip install pip-audit
  script:
    - pip-audit -r requirements.txt --format json --output gl-dependency-scanning-report.json || true
  artifacts:
    reports:
      dependency_scanning: gl-dependency-scanning-report.json

container_security_scan:
  stage: security
  image:
    name: aquasec/trivy:latest
    entrypoint: [""]
  variables:
    GIT_STRATEGY: none
  script:
    - trivy image --no-progress --format template --template "@/contrib/gitlab.tpl"
        --output gl-container-scanning-report.json clearance-check-canary:$CI_COMMIT_SHA
  artifacts:
    reports:
      container_scanning: gl-container-scanning-report.json
  rules:
    - if: '$CI_COMMIT_TAG =~ /^v.*-canary\..*$/'

# ------------------------------------------------------------------------------
# STAGE: package — Multi-Stage Container Build (C5)
# ------------------------------------------------------------------------------
build_container_image:
  stage: package
  image: docker:24.0.5
  services:
    - docker:24.0.5-dind
  before_script:
    - docker info
  script:
    - docker build -f Dockerfile.canary -t clearance-check-canary:$CI_COMMIT_SHA .
    - docker run -d --name canary-health-test -p 8000:8000
        --read-only --tmpfs /tmp:rw,size=64m
        clearance-check-canary:$CI_COMMIT_SHA
    - sleep 5
    - docker exec canary-health-test python -c "import urllib.request; assert urllib.request.urlopen('http://localhost:8000/health').getcode() == 200"
    - docker stop canary-health-test

# ------------------------------------------------------------------------------
# STAGE: release — Canary Pre-Release Publication
# ------------------------------------------------------------------------------
publish_canary_release:
  stage: release
  image: registry.gitlab.com/gitlab-org/release-cli:latest
  rules:
    - if: '$CI_COMMIT_TAG =~ /^v.*-canary\..*$/'
  script:
    - echo "Publishing Clearance Check Canary $CI_COMMIT_TAG"
  release:
    tag_name: '$CI_COMMIT_TAG'
    name: 'Clearance Check Canary $CI_COMMIT_TAG'
    description: |
      **NOTICE: Canary build — for evaluation only. Not for screening decisions.**
      Prepared by: Antigravity (AI assistant) — for review by Sounit Karttikay.
```

---

## 4. Runner & Environment Configuration

### 4.1 GitLab Runner Tags
Enterprise runners should be equipped with:
- `docker` executor or `kubernetes` executor.
- Minimum resources: 2 vCPUs, 4 GB RAM per container job.
- Network policy: isolated runner network (egress restricted during test execution to ensure offline test independence).

### 4.2 Security Context
All container execution jobs enforce:
- Non-root UID: `10001` (`appuser`).
- Read-only root filesystem (`read_only: true`).
- Tmpfs mounted at `/tmp` (`size=64m,noexec,nosuid`).
- Volume mounts for persistent application state (`/var/lib/clearance-check`).

---

## 5. Branch & Tag Strategy

1. **Stable Branch:** `release/1.x`  
   - Builds stable desktop installer `ClearanceCheck-Setup-v1.x.exe`.  
   - Tagged as `v1.x.y`.
2. **Canary Branch:** `main` (and `wip/canary.N`)  
   - Builds canary server container and side-by-side desktop client.  
   - Tagged as `v2.0.1-canary.N`.  
   - GitLab releases are automatically marked as **Pre-release** with permanent disclaimer notices.
