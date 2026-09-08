"""Validated, inspectable Cloud Run Job configuration without secret values."""

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROLES = ("worker", "analysis-dispatch", "activity", "lore", "notifications")
ENV_KEYS = {
    "DOCAI_PROCESSOR_ID",
    "GEMINI_MODEL",
    "GEMINI_MODEL_LITE",
    "CLICKHOUSE_HOST",
    "CLICKHOUSE_USER",
    "VERTEX_SEARCH_DATA_STORE_ID",
    "SCRIPTS_INTAKE_BUCKET",
    "CLEARCUT_PROVIDER_OPTIONS",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
}
FLEXIBLE_KEYS = {"CLICKHOUSE_HOST", "CLICKHOUSE_USER", "OTEL_EXPORTER_OTLP_ENDPOINT"}
SECRET_KEYS = {
    "PARALLEL_API_KEY",
    "CLICKHOUSE_PASSWORD",
    "NOTIFY_WEBHOOK_URL",
    "OTEL_EXPORTER_OTLP_HEADERS",
}
SECRET_KEYS |= FLEXIBLE_KEYS
REQUIRED_ENV = ENV_KEYS - FLEXIBLE_KEYS - {"CLEARCUT_PROVIDER_OPTIONS"}
REQUIRED_SECRETS = SECRET_KEYS - FLEXIBLE_KEYS - {"OTEL_EXPORTER_OTLP_HEADERS"}


def validate(value: dict[str, Any]) -> dict[str, Any]:
    if set(value) != {
        "project",
        "region",
        "image",
        "job_prefix",
        "accounts",
        "environment",
        "secret_versions",
    }:
        raise ValueError("runtime manifest must contain only the documented fields")
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", value.get("project", "")):
        raise ValueError("invalid GCP project")
    if not re.fullmatch(r"[a-z]+-[a-z]+[0-9]", value.get("region", "")):
        raise ValueError("invalid GCP region")
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,35}", value.get("job_prefix", "")):
        raise ValueError("invalid dedicated job prefix")
    if not re.fullmatch(r"[A-Za-z0-9./_-]+@sha256:[0-9a-f]{64}", value.get("image", "")):
        raise ValueError("an immutable image digest is required")
    accounts = value["accounts"]
    if not isinstance(accounts, dict) or set(accounts) != {*ROLES, "scheduler"}:
        raise ValueError("supply existing service accounts for all five jobs and the scheduler")
    suffix = "@" + value["project"] + ".iam.gserviceaccount.com"
    if any(
        not isinstance(account, str)
        or not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]" + re.escape(suffix), account)
        for account in accounts.values()
    ):
        raise ValueError("service accounts must belong to the selected project")
    environment, secrets = value["environment"], value["secret_versions"]
    if not isinstance(environment, dict) or not REQUIRED_ENV <= set(environment) <= ENV_KEYS:
        raise ValueError("missing or unknown non-secret runtime environment keys")
    if any(not isinstance(item, str) or not item.strip() for item in environment.values()):
        raise ValueError("runtime environment values must be nonblank strings")
    if not isinstance(secrets, dict) or not REQUIRED_SECRETS <= set(secrets) <= SECRET_KEYS:
        raise ValueError("required secrets must be named by pinned Secret Manager version")
    if set(environment) & set(secrets):
        raise ValueError(
            "runtime keys must use either public environment or secret reference, not both"
        )
    if not {"CLICKHOUSE_HOST", "CLICKHOUSE_USER"} <= set(environment) | set(secrets):
        raise ValueError(
            "ClickHouse host and user require a public value or pinned secret reference"
        )
    if any(
        not isinstance(item, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,255}:[1-9][0-9]*", item)
        for item in secrets.values()
    ):
        raise ValueError(
            "secret references require explicit numeric versions, never values or latest"
        )
    return value


def jobs(config: dict[str, Any], output: Path) -> list[dict[str, Any]]:
    validate(config)
    values = []
    modules = {
        "worker": "worker",
        "analysis-dispatch": "dispatcher",
        "activity": "activity_dispatcher",
        "lore": "lore_dispatcher",
        "notifications": "notification_dispatcher",
    }
    public = config["environment"]
    for role in ROLES:
        name = config["job_prefix"] + "-" + role
        environment = {"GOOGLE_CLOUD_PROJECT": config["project"]}
        secrets: dict[str, str] = {}
        if role == "worker":
            environment.update(public)
            environment["CLEARCUT_MODE"] = "live"
            secrets.update(config["secret_versions"])
        elif role == "analysis-dispatch":
            environment.update(
                {
                    "CLOUD_RUN_REGION": config["region"],
                    "CLEARCUT_ANALYSIS_JOB": config["job_prefix"] + "-worker",
                }
            )
        elif role == "activity":
            for key in ("CLICKHOUSE_HOST", "CLICKHOUSE_USER"):
                if key in public:
                    environment[key] = public[key]
                else:
                    secrets[key] = config["secret_versions"][key]
            secrets["CLICKHOUSE_PASSWORD"] = config["secret_versions"]["CLICKHOUSE_PASSWORD"]
        elif role == "lore":
            environment["SCRIPTS_INTAKE_BUCKET"] = public["SCRIPTS_INTAKE_BUCKET"]
        else:
            secrets["NOTIFY_WEBHOOK_URL"] = config["secret_versions"]["NOTIFY_WEBHOOK_URL"]
        args = ["-m", "clearcut." + modules[role]]
        if role == "worker":
            args.extend(["--analysis-id", "requires-dispatcher-override"])
        timeout = "3600" if role == "worker" else "1800" if role == "lore" else "600"
        job = {
            "name": name,
            "role": role,
            "image": config["image"],
            "args": args,
            "environment": environment,
            "secrets": secrets,
            "service_account": config["accounts"][role],
            "timeout": timeout,
            "memory": "2Gi" if role == "worker" else "1Gi",
            "cpu": "2" if role == "worker" else "1",
        }
        digest = hashlib.sha256(json.dumps(job, sort_keys=True).encode()).hexdigest()[:32]
        env_file = output / (role + ".env.json")
        command = [
            "gcloud",
            "run",
            "jobs",
            "deploy",
            name,
            "--project",
            config["project"],
            "--region",
            config["region"],
            "--image",
            config["image"],
            "--service-account",
            job["service_account"],
            "--command",
            "python",
            "--args",
            ",".join(args),
            "--tasks",
            "1",
            "--parallelism",
            "1",
            "--max-retries",
            "0",
            "--task-timeout",
            timeout + "s",
            "--memory",
            job["memory"],
            "--cpu",
            job["cpu"],
            "--env-vars-file",
            str(env_file),
            "--labels",
            "clearcut-recovery=true,clearcut-plan=" + digest,
            "--format=json",
            "--quiet",
        ]
        command.extend(
            ["--set-secrets", ",".join(key + "=" + ref for key, ref in sorted(secrets.items()))]
            if secrets
            else ["--clear-secrets"]
        )
        values.append(
            {**job, "plan_hash": digest, "environment_file": str(env_file), "command": command}
        )
    return values


def job_binding(config: dict[str, Any], job_name: str, account: str, role: str) -> list[str]:
    return [
        "gcloud",
        "run",
        "jobs",
        "add-iam-policy-binding",
        job_name,
        "--project",
        config["project"],
        "--region",
        config["region"],
        "--member",
        "serviceAccount:" + account,
        "--role",
        role,
        "--format=json",
        "--quiet",
    ]


def execution_bindings(config: dict[str, Any], job_values: list[dict[str, Any]]) -> list[list[str]]:
    commands = [
        job_binding(
            config,
            config["job_prefix"] + "-worker",
            config["accounts"]["analysis-dispatch"],
            "roles/run.jobsExecutorWithOverrides",
        )
    ]
    commands.extend(
        job_binding(config, job["name"], config["accounts"]["scheduler"], "roles/run.jobsExecutor")
        for job in job_values
        if job["role"] != "worker"
    )
    return commands


def scheduler_command(config: dict[str, Any], job: dict[str, Any], existing: bool) -> list[str]:
    return [
        "gcloud",
        "scheduler",
        "jobs",
        "update" if existing else "create",
        "http",
        job["name"] + "-schedule",
        "--project",
        config["project"],
        "--location",
        config["region"],
        "--schedule",
        "* * * * *",
        "--time-zone",
        "Etc/UTC",
        "--uri",
        f"https://run.googleapis.com/v2/projects/{config['project']}/locations/{config['region']}/jobs/{job['name']}:run",
        "--http-method",
        "POST",
        "--message-body",
        "{}",
        "--headers",
        "Content-Type=application/json",
        "--oauth-service-account-email",
        config["accounts"]["scheduler"],
        "--oauth-token-scope",
        "https://www.googleapis.com/auth/cloud-platform",
        "--attempt-deadline",
        "30s",
        "--max-retry-attempts",
        "0",
        "--description",
        "ClearCut recovery scheduler v1",
        "--format=json",
        "--quiet",
    ]
