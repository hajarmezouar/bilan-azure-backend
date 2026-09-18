# Azure Quiz — Spring Boot Backend

REST API for Azure Quiz. It provides certifications, modules, questions, quiz sessions and results to the Angular frontend.

## Status

- API: [https://app-azure-quiz-backend-nonprod.azurewebsites.net](https://app-azure-quiz-backend-nonprod.azurewebsites.net)
- Health: [`/actuator/health`](https://app-azure-quiz-backend-nonprod.azurewebsites.net/actuator/health)
- GitHub Actions pipeline validated through tests, build, scans, ACR publication, Web App deployment and smoke tests.
- Production image is immutable and tagged with the Git commit SHA.

## Application architecture

![Azure Quiz backend architecture](docs/application-architecture.png)

Editable source: [application-architecture.drawio](docs/application-architecture.drawio).

```text
Angular / Azure Linux Web App container
              |
              | HTTPS REST API
              v
Spring Boot / Azure Linux Web App
              |
              +--> PostgreSQL: persistent data
              +--> Redis: application cache
              +--> Blob Storage: JSON result exports
              +--> Key Vault: PostgreSQL and Redis secrets
```

The backend is the only component allowed to access data services. In Azure, it uses VNet Integration, Private Endpoints and private DNS. Its managed identity avoids ACR and Storage keys in application configuration.

The complete infrastructure is maintained in `bilan-azure-terraform`.

## Technology

- Java 21 and Spring Boot 3.5;
- Spring Web, Spring Data JPA and Bean Validation;
- PostgreSQL and Flyway;
- Spring Data Redis;
- Azure Blob Storage;
- Actuator and springdoc-openapi;
- Maven, JUnit 5, Mockito and AssertJ;
- multi-stage Docker image running as a non-root user.

## Run locally

Prerequisites: JDK 21 and Docker.

```bash
./mvnw spring-boot:run
```

Spring Boot Docker Compose automatically starts PostgreSQL, Redis and Azurite from `docker-compose.yml`. The API runs on `http://localhost:8080`, and Swagger UI is available at `http://localhost:8080/swagger-ui.html`.

To manage the containers manually:

```bash
docker compose up -d
./mvnw spring-boot:run
```

Run tests only:

```bash
./mvnw test
```

## Data and behavior

Flyway creates the schema and loads certifications, modules and questions at startup. PostgreSQL remains the source of truth. Redis caches certifications and modules for 30 minutes.

Reading a quiz result also exports a JSON document to the `application-files` Blob container. A Storage failure is logged but does not prevent the quiz from completing.

## Main API endpoints

- `GET /api/certifications`
- `GET /api/certifications/{certificationId}/modules`
- `POST /api/quiz-sessions`
- `POST /api/quiz-sessions/{sessionId}/questions/{questionId}/answer`
- `GET /api/quiz-sessions/{sessionId}/result`
- `GET /api/quiz-sessions/{sessionId}/result/export`

Question responses do not reveal the correct answer before submission.

## Azure configuration

Terraform injects the main settings into Azure Web App:

| Variable | Purpose |
|---|---|
| `SPRING_DATASOURCE_URL` | TLS connection to private PostgreSQL |
| `SPRING_DATASOURCE_USERNAME` | PostgreSQL user |
| `SPRING_DATASOURCE_PASSWORD` | Key Vault secret reference |
| `REDIS_HOSTNAME`, `REDIS_PORT` | Private Redis endpoint |
| `REDIS_PASSWORD` | Key Vault secret reference |
| `REDIS_SSL_ENABLED` | Enables Redis TLS |
| `STORAGE_ACCOUNT_NAME` | Blob account accessed with managed identity |
| `STORAGE_CONTAINER_NAME` | `application-files` container |
| `APP_CORS_ALLOWED_ORIGINS` | Exact allowed frontend origin |
| `SPRING_PROFILES_ACTIVE` | `prod` profile in Azure |

No application secret is built into the Docker image.

## CI/CD pipeline

The `backend-cicd.yml` workflow validates and deploys the application:

1. Maven compilation and unit tests;
2. Docker image build;
3. publication of the reviewed image to Azure Container Registry;
4. Azure authentication through GitHub OIDC;
5. deployment of the exact Git-SHA-tagged image to Azure Linux Web App;
6. `/actuator/health` verification and API smoke tests.

Pull Requests build and validate the application without Azure deployment permissions.

Pushes to `main` deploy to `nonprod`. Production deployment is selected explicitly from **Actions > Backend CI/CD > Run workflow** and uses the protected GitHub environment `prod`.

The deployed image is tagged with the Git commit SHA, providing traceability between the source revision, the ACR image and the version running in Azure.

Post-deployment DAST is triggered only after a successful `Backend CI/CD` run. This prevents the dynamic scan from racing the Azure deployment or scanning a stopped/outdated application.

Required GitHub environment variables:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_RESOURCE_GROUP`
- `AZURE_ACR_NAME`
- `AZURE_WEBAPP_NAME`

These are non-secret identifiers. GitHub authenticates to Azure through OIDC, so the pipeline does not store an Azure client secret, publish profile or ACR password.

## DevSecOps and security

Security controls are separated into five dedicated GitHub Actions workflows. Each workflow covers a different security category and exposes its result independently.

| Category | Tool | Scope | Policy |
| --- | --- | --- | --- |
| SAST | SonarQube Cloud | Java / Spring Boot source code | Static analysis and Quality Gate |
| SCA | Trivy | Maven dependencies | Fixable HIGH/CRITICAL vulnerabilities are blocking |
| Secrets | Gitleaks | Repository and Git history | Detected secrets are blocking |
| Container | Trivy | Docker image and configuration | HIGH/CRITICAL findings are blocking |
| DAST | OWASP ZAP Baseline | Deployed nonprod API | Informational baseline |

### SAST — SonarQube Cloud

SonarQube Cloud performs static analysis of the Java/Spring Boot code.

The workflow:

1. builds the Maven project;
2. executes the unit tests;
3. generates a JaCoCo coverage report;
4. sends the source analysis and coverage report to SonarQube Cloud.

During the security review, SonarQube identified GitHub Actions referenced by mutable version tags. The affected actions were replaced with full commit SHA references.

This provides a reproducible workflow definition and reduces the risk associated with a mutable third-party Action reference.

The corrected workflow was then analyzed again through SonarQube Cloud.

### SCA — Trivy

Trivy performs Software Composition Analysis of the Maven dependencies.

The workflow focuses its blocking policy on fixable `HIGH` and `CRITICAL` vulnerabilities.

Vulnerabilities without an available upstream fix can still be reported, but they are not treated as immediately remediable failures.

### Secret detection — Gitleaks

Gitleaks scans the repository and its Git history for accidentally committed credentials, API keys, tokens and other secrets.

The workflow checks the complete Git history rather than only the latest commit.

A confirmed secret detection is considered blocking.

### Container security — Trivy

The production Docker image is analyzed by Trivy before deployment.

The analysis covers:

- operating-system packages;
- application packages;
- HIGH and CRITICAL vulnerabilities;
- Docker and configuration security issues.

The application container runs as a non-root user and contains no application credentials.

### DAST — OWASP ZAP

OWASP ZAP Baseline performs dynamic security testing against the deployed non-production backend.

Unlike source-based scans, DAST requires a running application. It is therefore triggered only after a successful `Backend CI/CD` workflow:

```text
Backend CI/CD
     |
     v
Deploy to Azure
     |
     v
Health verification
     |
     v
OWASP ZAP