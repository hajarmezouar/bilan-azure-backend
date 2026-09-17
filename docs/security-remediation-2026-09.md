# Container dependency remediation — September 2026

The Azure recovery deployment was blocked by the existing Trivy image gate in [run 35202590213](https://github.com/hajarmezouar/bilan-azure-backend/actions/runs/35202590213), scanning commit `883983d034df48af72489d64afa122702c78792c`.

| Packaged dependency | Finding reported by Trivy | Before | Corrected version |
|---|---|---|---|
| netty-handler | CVE-2026-75595 | 4.1.136.Final | 4.1.137.Final |
| tomcat-embed-core | CVE-2026-65182, CVE-2026-65905, CVE-2026-68525 | 10.1.55 | 10.1.59 |

These are vulnerable packaged dependencies, not proof that every affected feature is exploitable through this application's routes. Trivy classified the four findings as critical; upstream severity ratings may differ.

The correction overrides Spring Boot's managed Netty and Tomcat versions within the existing 4.1 and 10.1 compatibility lines. All artifacts in each managed family use the same override. No finding is suppressed and the existing blocking image scan remains enabled.

Sources consulted before the change:
- [Netty 4.1.137.Final release](https://github.com/netty/netty/releases/tag/netty-4.1.137.Final).
- [Apache Tomcat 10 security advisories](https://tomcat.apache.org/security-10.html): 10.1.58 did not pass its release vote; 10.1.59 is the released version containing those fixes.

Validation required: Maven tests, production Docker build, the same Trivy image gate, and the nonprod Azure health check after deployment. Results will be linked after the workflows complete.
