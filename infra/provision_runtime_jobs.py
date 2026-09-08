"""Plan dedicated recovery Jobs; schedule activation is an explicit separate step."""

import argparse
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from infra.provision_runtime_indexes import reconcile as index_status
from infra.runtime_job_plan import execution_bindings, jobs, scheduler_command, validate

Runner = Callable[[list[str]], Any]


def command(arguments: list[str]) -> Any:
    result = subprocess.run(arguments, capture_output=True, text=True, timeout=180, check=False)
    if result.returncode:
        if "describe" in arguments and "(NOT_FOUND)" in result.stderr:
            return None
        raise RuntimeError(
            "runtime provisioning operation failed; inspect named resource before retry"
        )
    try:
        return json.loads(result.stdout or "null")
    except ValueError:
        raise RuntimeError("runtime provisioning response could not be verified") from None


def describe(config: dict[str, Any], job: dict[str, Any], run: Runner) -> dict[str, Any] | None:
    value = run(
        [
            "gcloud",
            "run",
            "jobs",
            "describe",
            job["name"],
            "--project",
            config["project"],
            "--region",
            config["region"],
            "--format=json",
            "--quiet",
        ]
    )
    if value is not None and not isinstance(value, dict):
        raise RuntimeError("unexpected Cloud Run Job representation")
    return value


def matches(value: dict[str, Any], job: dict[str, Any]) -> bool:
    # gcloud's Cloud Run v1 export shape; unknown shapes never count as verified.
    try:
        template = value["spec"]["template"]["spec"]
        task = template["template"]["spec"]
        containers = task["containers"]
        if len(containers) != 1:
            return False
        container = containers[0]
        environment, secrets = {}, {}
        for entry in container.get("env", []):
            if "value" in entry:
                environment[entry["name"]] = entry["value"]
            else:
                secret = entry["valueFrom"]["secretKeyRef"]
                secrets[entry["name"]] = secret["name"] + ":" + str(secret["key"])
        return (
            container["image"] == job["image"]
            and container["command"] == ["python"]
            and container["args"] == job["args"]
            and environment == job["environment"]
            and secrets == job["secrets"]
            and task["serviceAccountName"] == job["service_account"]
            and str(task["timeoutSeconds"]) == job["timeout"]
            and int(task["maxRetries"]) == 0
            and int(template["taskCount"]) == 1
            and int(template["parallelism"]) == 1
            and container["resources"]["limits"] == {"cpu": job["cpu"], "memory": job["memory"]}
        )
    except (KeyError, TypeError, ValueError):
        return False


def ready(value: dict[str, Any]) -> bool:
    return any(
        condition.get("type") == "Ready" and condition.get("status") in {True, "True"}
        for condition in value.get("status", {}).get("conditions", [])
    )


def provision_jobs(
    config: dict[str, Any], values: list[dict[str, Any]], run: Runner = command
) -> list[dict[str, Any]]:
    if any(
        index["state"] != "READY" for index in index_status(config["project"], apply=False, run=run)
    ):
        raise RuntimeError("all runtime indexes must be READY before configuring jobs")
    result = []
    for job in values:
        existing = describe(config, job, run)
        if (
            existing is not None
            and existing.get("metadata", {}).get("labels", {}).get("clearcut-recovery") != "true"
        ):
            raise RuntimeError(
                "refusing to overwrite a job not owned by this recovery configuration"
            )
        if existing is None or not matches(existing, job):
            run(job["command"])
            existing = describe(config, job, run)
        if existing is None or not matches(existing, job) or not ready(existing):
            raise RuntimeError(
                "job configuration is not yet verified ready; schedules remain unchanged"
            )
        result.append(
            {"name": job["name"], "state": "CONFIGURATION_VERIFIED", "execution_verified": False}
        )
    for binding in execution_bindings(config, values):
        run(binding)
    return result


def schedule_matches(current: dict[str, Any], config: dict[str, Any], uri: str) -> bool:
    target = current.get("httpTarget", {})
    token = target.get("oauthToken", {})
    headers = {name.lower(): value for name, value in target.get("headers", {}).items()}
    return (
        current.get("schedule") == "* * * * *"
        and current.get("timeZone") == "Etc/UTC"
        and target.get("uri") == uri
        and target.get("httpMethod") == "POST"
        and target.get("body") == "e30="
        and token.get("serviceAccountEmail") == config["accounts"]["scheduler"]
        and token.get("scope") == "https://www.googleapis.com/auth/cloud-platform"
        and headers.get("content-type") == "application/json"
        and current.get("retryConfig", {}).get("retryCount", 0) == 0
    )


def activate_schedules(
    config: dict[str, Any], values: list[dict[str, Any]], run: Runner = command
) -> list[str]:
    if any(
        index["state"] != "READY" for index in index_status(config["project"], apply=False, run=run)
    ):
        raise RuntimeError("runtime indexes are not ready")
    for job in values:
        current = describe(config, job, run)
        if (
            current is None
            or not matches(current, job)
            or not ready(current)
            or current.get("metadata", {}).get("labels", {}).get("clearcut-recovery") != "true"
        ):
            raise RuntimeError("all job configurations must match before activating schedules")
    for binding in execution_bindings(config, values):
        name = binding[4]
        policy = run(
            [
                "gcloud",
                "run",
                "jobs",
                "get-iam-policy",
                name,
                "--project",
                config["project"],
                "--region",
                config["region"],
                "--format=json",
                "--quiet",
            ]
        )
        member, role = binding[binding.index("--member") + 1], binding[binding.index("--role") + 1]
        if not any(
            entry.get("role") == role
            and member in entry.get("members", [])
            and not entry.get("condition")
            for entry in policy.get("bindings", [])
        ):
            raise RuntimeError("scoped job execution permission is missing")
    activated = []
    for job in values:
        if job["role"] == "worker":
            continue
        description = [
            "gcloud",
            "scheduler",
            "jobs",
            "describe",
            job["name"] + "-schedule",
            "--project",
            config["project"],
            "--location",
            config["region"],
            "--format=json",
            "--quiet",
        ]
        existing = run(description)
        if existing and existing.get("description") != "ClearCut recovery scheduler v1":
            raise RuntimeError("refusing to replace an unowned scheduler job")
        desired = scheduler_command(config, job, existing is not None)
        expected_uri = desired[desired.index("--uri") + 1]
        if not existing or not schedule_matches(existing, config, expected_uri):
            run(desired)
            current = run(description)
        else:
            current = existing
        if current and current.get("state") == "PAUSED":
            run(
                [
                    "gcloud",
                    "scheduler",
                    "jobs",
                    "resume",
                    job["name"] + "-schedule",
                    "--project",
                    config["project"],
                    "--location",
                    config["region"],
                    "--format=json",
                    "--quiet",
                ]
            )
            current = run(description)
        if (
            not current
            or current.get("state") != "ENABLED"
            or not schedule_matches(current, config, expected_uri)
        ):
            raise RuntimeError("schedule activation could not be verified; do not blindly retry")
        activated.append(job["name"])
    return activated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Directory for inspectable non-secret environment files and plan",
    )
    phase = parser.add_mutually_exclusive_group()
    phase.add_argument("--apply-jobs", action="store_true")
    phase.add_argument(
        "--activate-schedules",
        action="store_true",
        help="Starts recurring execution and provider work",
    )
    args = parser.parse_args()
    config = validate(json.loads(args.manifest.read_text()))
    values = jobs(config, args.output)
    args.output.mkdir(parents=True, exist_ok=True)
    for job in values:
        Path(job["environment_file"]).write_text(json.dumps(job["environment"], indent=2) + "\n")
    plan = {
        "jobs": values,
        "execution_bindings": execution_bindings(config, values),
        "schedule_activation": [
            scheduler_command(config, job, False) for job in values if job["role"] != "worker"
        ],
        "creates_service_accounts": False,
        "deploys_http_service": False,
        "default_makes_cloud_calls": False,
        "activation_starts_recurring_provider_work": True,
    }
    (args.output / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    if args.apply_jobs:
        print(json.dumps(provision_jobs(config, values), indent=2))
    elif args.activate_schedules:
        print(json.dumps({"activated": activate_schedules(config, values)}, indent=2))
    else:
        print(json.dumps({"plan": str(args.output / "plan.json"), "cloud_calls": False}))


if __name__ == "__main__":
    main()
