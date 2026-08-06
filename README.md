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
Angular / Azure Static Web Apps
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

The [backend-cicd.yml](.github/workflows/backend-cicd.yml) workflow performs:

1. Maven compilation and tests;
2. Docker image build;
3. source, dependency, secret and image scans;
4. Azure authentication through GitHub OIDC;
5. publication to `acrhmezouarquiznonprod` using the Git SHA as the tag;
6. deployment of that exact image to Azure Linux Web App;
7. `/actuator/health` verification and API smoke tests.

Pull Requests build and test without Azure permissions. Deployment runs from `main` through the protected GitHub environment `nonprod`.

Required GitHub environment variables:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_RESOURCE_GROUP`
- `AZURE_ACR_NAME`
- `AZURE_WEBAPP_NAME`

These are non-secret identifiers. The pipeline uses no client secret, publish profile or ACR password.

## Governance and security

- signed commits displayed as `Verified`;
- ownership declared in `CODEOWNERS`;
- Dependabot for Maven, Docker and GitHub Actions;
- Trivy and Gitleaks on every push and Pull Request;
- non-root runtime container;
- protected `main` branch and deployment restricted to `nonprod`.

A failed test, scan, deployment or health check blocks the workflow and makes the problem visible in GitHub Actions.
