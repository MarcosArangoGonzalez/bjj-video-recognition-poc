# AI Service Parity Integration

## Goal

Run `bjj-app` with the current `ai-service` while preserving the exact analysis behavior that is known to work in the PoC stack.

The authoritative analysis path is:

1. Flask YOLO PoC
2. Spring PoC
3. `ai-service` wrapper
4. `bjj-app` backend webhook

`ai-service` must not reinterpret detections. It only:

- receives the async analysis request from `bjj-app`
- forwards the video to the Spring PoC
- maps the returned tags into the webhook contract expected by `bjj-app`
- sends the webhook back to the main backend

## Default Startup

The normal startup entrypoint is now:

```bash
./scripts/run_bjj_stack.sh
```

By default it delegates to:

```bash
./scripts/run_parity_stack.sh
```

This starts:

- `bjj-app` backend on `8080`
- Flask YOLO PoC on `8091`
- Spring PoC on `8090`
- `ai-service` on `8081`
- `bjj-app` frontend on `3000`

## Dockerized Startup

If you want the whole parity topology under Docker:

```bash
./scripts/run_docker_parity_stack.sh
```

This uses:

- [docker-compose.parity.yml](/home/marcos/Escritorio/bjj-video-recognition-poc-main/docker-compose.parity.yml)
- [Dockerfile.spring-poc](/home/marcos/Escritorio/bjj-video-recognition-poc-main/Dockerfile.spring-poc)

Stop it with:

```bash
./scripts/stop_docker_parity_stack.sh
```

If you use Vertex AI Gemini inside the Spring PoC container, set:

- `GOOGLE_APPLICATION_CREDENTIALS_HOST_PATH`
- `GOOGLE_CLOUD_PROJECT_ID`
- `GOOGLE_CLOUD_LOCATION`

before `docker compose up`.

## Health Check

After startup:

```bash
curl http://localhost:8081/health
```

Expected fields:

- `pipeline_mode: spring_poc_wrapper`
- `spring_poc_enabled: true`
- `spring_poc_base_url: http://localhost:8090`

## Important Rule

Do not add new detection heuristics inside `ai-service` if parity with the PoC must be preserved.

If analysis quality changes, the first place to inspect is the PoC stack:

- Flask YOLO service
- Spring PoC analysis pipeline

Only after parity is proven should logic be extracted or rewritten.
