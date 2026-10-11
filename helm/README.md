# RAGFlow Helm Chart

A Helm chart to deploy RAGFlow and its dependencies on Kubernetes.

- Components: RAGFlow (web/api) and optional dependencies (Infinity/Elasticsearch/OpenSearch, MySQL, MinIO, Redis)
- Requirements: Kubernetes >= 1.24, Helm >= 3.10

## Install

Production installations should provision credentials outside Helm values. Create or synchronize a Secret containing the required keys, then point the chart at it:

```bash
kubectl create namespace ragflow --dry-run=client -o yaml | kubectl apply -f -
kubectl -n ragflow create secret generic ragflow-production-secrets \
  --from-env-file=/secure/runtime/ragflow-secrets.env
helm upgrade --install ragflow ./helm \
  --namespace ragflow \
  --set secrets.existingSecret=ragflow-production-secrets
```

The Secret must contain `RAGFLOW_SECRET_KEY`, `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD`, `MINIO_PASSWORD`, `MINIO_ROOT_PASSWORD`, `REDIS_PASSWORD`, and the active document-engine password (`ELASTIC_PASSWORD` or both `OPENSEARCH_PASSWORD` and `OPENSEARCH_INITIAL_ADMIN_PASSWORD`). Infinity does not require a document-engine password. Use External Secrets, Vault, or the platform secret manager in preference to the illustrative `kubectl create` command.

If `secrets.existingSecret` is empty, the chart can create its own Secret, but all corresponding `env.*` values are required and must be supplied from a protected values file that is never committed.

Uninstall:
```bash
helm uninstall ragflow -n ragflow
```

## Global Settings

- `global.repo`: Prepend a global image registry prefix for all images.
  - Behavior: Replaces the registry part and keeps the image path (e.g., `quay.io/minio/minio` -> `registry.example.com/myproj/minio/minio`).
  - Example: `global.repo: "registry.example.com/myproj"`
- `global.imagePullSecrets`: List of image pull secrets applied to all Pods.
  - Example:
    ```yaml
    global:
      imagePullSecrets:
        - name: regcred
    ```
- `secrets.existingSecret`: Name of a pre-created Secret used by every RAGFlow component. This is the recommended production path.

## External Services (MySQL / MinIO / Redis)

The chart can deploy in-cluster services or connect to external ones. Toggle with `*.enabled`. When disabled, provide host/port via `env.*`.

- MySQL
  - `mysql.enabled`: default `true`
  - If `false`, set:
    - `env.MYSQL_HOST` (required), `env.MYSQL_PORT` (default `3306`)
    - `env.MYSQL_DBNAME` (default `rag_flow`), `env.MYSQL_PASSWORD` (required)
    - `env.MYSQL_USER` (default `root` if omitted)
- MinIO
  - `minio.enabled`: default `true`
  - Configure:
    - `env.MINIO_HOST` (optional external host), `env.MINIO_PORT` (default `9000`)
    - `env.MINIO_ROOT_USER` (default `rag_flow`), `env.MINIO_PASSWORD` (required when the chart creates the Secret)
- Redis (Valkey)
  - `redis.enabled`: default `true`
  - If `false`, set:
    - `env.REDIS_HOST` (required), `env.REDIS_PORT` (default `6379`)
    - `env.REDIS_PASSWORD` (required when the chart creates the Secret)

Notes:
- When `*.enabled=true`, the chart renders in-cluster resources and injects corresponding `*_HOST`/`*_PORT` automatically.
- Runtime configuration is stored in a ConfigMap. Credentials are loaded from `secrets.existingSecret`, or from a chart-generated Secret when no external Secret is configured.

### Example: use external MySQL, MinIO, and Redis

```yaml
# values.override.yaml
mysql:
  enabled: false  # use external MySQL
minio:
  enabled: false  # use external MinIO (S3 compatible)
redis:
  enabled: false  # use external Redis/Valkey

secrets:
  existingSecret: ragflow-production-secrets

env:
  # MySQL
  MYSQL_HOST: mydb.example.com
  MYSQL_PORT: "3306"
  MYSQL_USER: root
  MYSQL_DBNAME: rag_flow

  # MinIO
  MINIO_HOST: s3.example.com
  MINIO_PORT: "9000"
  MINIO_ROOT_USER: rag_flow

  # Redis
  REDIS_HOST: redis.example.com
  REDIS_PORT: "6379"
```

Apply:
```bash
helm upgrade --install ragflow ./helm -n ragflow -f values.override.yaml
```

## Document Engine Selection

Choose one of `infinity` (default), `elasticsearch`, or `opensearch` via `env.DOC_ENGINE`. The chart renders only the selected engine and sets the appropriate host variables.

```yaml
env:
  DOC_ENGINE: infinity   # or: elasticsearch | opensearch
  # Engine credentials come from secrets.existingSecret.
```

## Ingress

Expose the web UI via Ingress:

```yaml
ingress:
  enabled: true
  className: nginx
  hosts:
    - host: ragflow.example.com
      paths:
        - path: /
          pathType: Prefix
```

## Validate the Chart

```bash
helm lint ./helm --set secrets.existingSecret=ragflow-production-secrets
helm template ragflow ./helm \
  --set secrets.existingSecret=ragflow-production-secrets > rendered.yaml
```

## Notes

- By default, the chart uses `DOC_ENGINE: infinity` and deploys in-cluster MySQL, MinIO, and Redis.
- The chart writes non-sensitive runtime settings to `<release>-ragflow-env-config` and reads credentials from the configured external Secret or `<release>-ragflow-env-secret`.
- `global.repo` and `global.imagePullSecrets` apply to all Pods; per-component `*.image.pullSecrets` still work and are merged with global settings.
