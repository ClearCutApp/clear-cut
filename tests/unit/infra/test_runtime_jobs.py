from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from infra.provision_runtime_jobs import activate_schedules, matches, provision_jobs
from infra.runtime_job_plan import ROLES, execution_bindings, jobs, scheduler_command, validate

from tests.unit.infra.test_runtime_indexes import inventory


def manifest() -> dict[str, Any]:
    return {
        "project": "project-id",
        "region": "us-central1",
        "image": "us-central1-docker.pkg.dev/project-id/recovery/app@sha256:" + "a" * 64,
        "job_prefix": "clearcut-recovery",
        "accounts": {
            role: "clearcut-" + role + "@project-id.iam.gserviceaccount.com"
            for role in (*ROLES, "scheduler")
        },
        "environment": {
            "DOCAI_PROCESSOR_ID": "processor",
            "GEMINI_MODEL": "model",
            "GEMINI_MODEL_LITE": "model-lite",
            "CLICKHOUSE_HOST": "host.example",
            "CLICKHOUSE_USER": "writer",
            "VERTEX_SEARCH_DATA_STORE_ID": "store",
            "SCRIPTS_INTAKE_BUCKET": "intake",
        },
        "secret_versions": {
            "PARALLEL_API_KEY": "parallel-key:1",
            "CLICKHOUSE_PASSWORD": "clickhouse-password:2",
            "NOTIFY_WEBHOOK_URL": "notify-url:3",
        },
    }


def remote(job: dict[str, Any]) -> dict[str, Any]:
    environment = [{"name": key, "value": value} for key, value in job["environment"].items()]
    for key, value in job["secrets"].items():
        name, version = value.split(":")
        environment.append(
            {"name": key, "valueFrom": {"secretKeyRef": {"name": name, "key": version}}}
        )
    return {
        "metadata": {"labels": {"clearcut-recovery": "true", "clearcut-plan": job["plan_hash"]}},
        "spec": {
            "template": {
                "spec": {
                    "taskCount": 1,
                    "parallelism": 1,
                    "template": {
                        "spec": {
                            "serviceAccountName": job["service_account"],
                            "timeoutSeconds": job["timeout"],
                            "maxRetries": 0,
                            "containers": [
                                {
                                    "image": job["image"],
                                    "command": ["python"],
                                    "args": job["args"],
                                    "env": environment,
                                    "resources": {
                                        "limits": {"cpu": job["cpu"], "memory": job["memory"]}
                                    },
                                }
                            ],
                        }
                    },
                }
            }
        },
        "status": {"conditions": [{"type": "Ready", "status": "True"}]},
    }


def test_plan_uses_packaged_entrypoints_no_execution_and_minimum_job_secret_sets():
    config = manifest()
    values = jobs(config, Path("plan"))
    assert len(values) == 5
    assert values[0]["args"] == [
        "-m",
        "clearcut.worker",
        "--analysis-id",
        "requires-dispatcher-override",
    ]
    for job in values:
        assert "--execute-now" not in job["command"] and "--wait" not in job["command"]
        assert job["command"][job["command"].index("--max-retries") + 1] == "0"
        assert "--env-vars-file" in job["command"]
    assert values[1]["secrets"] == {} and values[3]["secrets"] == {}
    assert set(values[2]["secrets"]) == {"CLICKHOUSE_PASSWORD"}
    assert set(values[4]["secrets"]) == {"NOTIFY_WEBHOOK_URL"}
    bindings = execution_bindings(config, values)
    assert len(bindings) == 5 and "roles/run.jobsExecutorWithOverrides" in bindings[0]
    assert all(
        command[:4] == ["gcloud", "run", "jobs", "add-iam-policy-binding"] for command in bindings
    )
    assert all("roles/run.developer" not in command for command in bindings)
    scheduler = scheduler_command(config, values[1], False)
    assert (
        "--oauth-service-account-email" in scheduler
        and "--oidc-service-account-email" not in scheduler
    )
    assert scheduler[scheduler.index("--uri") + 1].endswith(":run")


@pytest.mark.parametrize(
    "change", ["mutable-image", "secret-value", "latest-secret", "foreign-account", "unknown-env"]
)
def test_manifest_refuses_ambiguous_images_credentials_or_scope(change):
    value = manifest()
    if change == "mutable-image":
        value["image"] = "gcr.io/project-id/app:latest"
    if change == "secret-value":
        value["secret_versions"]["PARALLEL_API_KEY"] = "private-value"
    if change == "latest-secret":
        value["secret_versions"]["PARALLEL_API_KEY"] = "parallel-key:latest"
    if change == "foreign-account":
        value["accounts"]["worker"] = "worker@foreign.iam.gserviceaccount.com"
    if change == "unknown-env":
        value["environment"]["PASSWORD"] = "private"
    with pytest.raises(ValueError):
        validate(value)


def test_existing_exact_job_is_not_redeployed_but_external_config_change_is_detected():
    config = manifest()
    values = jobs(config, Path("plan"))
    snapshots = {job["name"]: remote(job) for job in values}

    def run(arguments):
        if "indexes" in arguments:
            return inventory()
        if "describe" in arguments:
            return snapshots[arguments[4]]
        assert "add-iam-policy-binding" in arguments
        return {}

    tracked = Mock(side_effect=run)
    result = provision_jobs(config, values, tracked)
    assert len(result) == 5 and all(value["execution_verified"] is False for value in result)
    assert not any("deploy" in call.args[0] for call in tracked.call_args_list)
    changed = deepcopy(snapshots[values[0]["name"]])
    changed["spec"]["template"]["spec"]["template"]["spec"]["containers"][0]["image"] = (
        "other-image"
    )
    assert not matches(changed, values[0])


def test_unready_indexes_or_unowned_existing_job_prevent_deployment():
    config = manifest()
    values = jobs(config, Path("plan"))
    run = Mock(return_value=inventory("CREATING"))
    with pytest.raises(RuntimeError):
        provision_jobs(config, values, run)
    assert run.call_count == 1
    run = Mock(side_effect=[inventory(), {"metadata": {"labels": {}}}])
    with pytest.raises(RuntimeError):
        provision_jobs(config, values, run)
    assert run.call_count == 2


def test_schedule_activation_checks_configuration_and_scoped_iam_before_any_write():
    config = manifest()
    values = jobs(config, Path("plan"))
    snapshots = {job["name"]: remote(job) for job in values}

    def run(arguments):
        if "indexes" in arguments:
            return inventory()
        if "describe" in arguments:
            return snapshots[arguments[4]]
        if "get-iam-policy" in arguments:
            return {"bindings": []}
        pytest.fail("schedule must not be activated without scoped IAM")

    with pytest.raises(RuntimeError):
        activate_schedules(config, values, run)


def test_default_cli_writes_only_non_secret_plan_without_cloud_calls(tmp_path, monkeypatch):
    import json

    from infra import provision_runtime_jobs

    source = tmp_path / "manifest.json"
    source.write_text(json.dumps(manifest()))
    output = tmp_path / "plan"
    monkeypatch.setattr("sys.argv", ["runtime", "--manifest", str(source), "--output", str(output)])
    monkeypatch.setattr(
        "subprocess.run", lambda *args, **kwargs: pytest.fail("default must remain offline")
    )
    provision_runtime_jobs.main()
    plan = json.loads((output / "plan.json").read_text())
    assert plan["default_makes_cloud_calls"] is False and len(plan["schedule_activation"]) == 4
    environment = json.loads((output / "worker.env.json").read_text())
    assert "PARALLEL_API_KEY" not in environment and "NOTIFY_WEBHOOK_URL" not in environment


def test_new_job_is_read_back_before_execution_permissions_and_never_started():
    config = manifest()
    values = jobs(config, Path("plan"))
    snapshots = {job["name"]: remote(job) for job in values[1:]}
    mutations = []

    def run(arguments):
        if "indexes" in arguments:
            return inventory()
        if "describe" in arguments:
            return snapshots.get(arguments[4])
        mutations.append(arguments)
        if "deploy" in arguments:
            snapshots[arguments[4]] = remote(values[0])
        return {}

    result = provision_jobs(config, values, run)
    assert len(result) == 5
    assert sum("deploy" in args for args in mutations) == 1
    assert not any("execute" in args or "--execute-now" in args for args in mutations)


def test_schedule_activation_is_idempotent_and_explicitly_resumes_owned_pause():
    config = manifest()
    values = jobs(config, Path("plan"))
    snapshots = {job["name"]: remote(job) for job in values}
    schedules: dict[str, Any] = {}
    mutations = []
    bindings = execution_bindings(config, values)

    def run(arguments):
        if "indexes" in arguments:
            return inventory()
        if arguments[1:3] == ["run", "jobs"]:
            if "describe" in arguments:
                return snapshots[arguments[4]]
            binding = next(value for value in bindings if value[4] == arguments[4])
            return {
                "bindings": [
                    {
                        "role": binding[binding.index("--role") + 1],
                        "members": [binding[binding.index("--member") + 1]],
                    }
                ]
            }
        if "describe" in arguments:
            return schedules.get(arguments[4])
        mutations.append(arguments)
        if "resume" in arguments:
            schedules[arguments[4]]["state"] = "ENABLED"
            return {}
        name = arguments[5]
        schedules[name] = {
            "description": "ClearCut recovery scheduler v1",
            "state": "ENABLED",
            "schedule": "* * * * *",
            "timeZone": "Etc/UTC",
            "httpTarget": {
                "uri": arguments[arguments.index("--uri") + 1],
                "httpMethod": "POST",
                "body": "e30=",
                "headers": {"Content-Type": "application/json"},
                "oauthToken": {
                    "serviceAccountEmail": config["accounts"]["scheduler"],
                    "scope": "https://www.googleapis.com/auth/cloud-platform",
                },
            },
        }
        return {}

    assert len(activate_schedules(config, values, run)) == 4 and len(mutations) == 4
    mutations.clear()
    assert len(activate_schedules(config, values, run)) == 4 and not mutations
    first = next(iter(schedules))
    schedules[first]["state"] = "PAUSED"
    activate_schedules(config, values, run)
    assert len(mutations) == 1 and "resume" in mutations[0]


@pytest.mark.parametrize("host_secret,user_secret", [(True, True), (True, False), (False, True)])
def test_existing_secret_backed_configuration_retains_minimum_job_distribution(
    tmp_path, host_secret, user_secret
):
    config = manifest()
    for key, selected in (("CLICKHOUSE_HOST", host_secret), ("CLICKHOUSE_USER", user_secret)):
        if selected:
            config["environment"].pop(key)
            config["secret_versions"][key] = key.lower() + ":7"
    config["secret_versions"]["OTEL_EXPORTER_OTLP_ENDPOINT"] = "otel-endpoint:9"
    planned = {job["role"]: job for job in jobs(config, tmp_path)}
    for key, selected in (("CLICKHOUSE_HOST", host_secret), ("CLICKHOUSE_USER", user_secret)):
        for role in ("worker", "activity"):
            assert (key in planned[role]["secrets"]) is selected
            assert (key in planned[role]["environment"]) is not selected
        for role in ("analysis-dispatch", "lore", "notifications"):
            assert key not in planned[role]["secrets"]
            assert key not in planned[role]["environment"]
    assert planned["worker"]["secrets"]["OTEL_EXPORTER_OTLP_ENDPOINT"] == "otel-endpoint:9"
    assert all(
        "OTEL_EXPORTER_OTLP_ENDPOINT" not in planned[role]["secrets"]
        for role in ROLES
        if role != "worker"
    )
    for job in planned.values():
        assert matches(remote(job), job)


@pytest.mark.parametrize(
    "key", ["CLICKHOUSE_HOST", "CLICKHOUSE_USER", "OTEL_EXPORTER_OTLP_ENDPOINT"]
)
@pytest.mark.parametrize("invalid", ["duplicate", "latest", "raw-value"])
def test_flexible_config_never_accepts_ambiguous_or_unpinned_secret_values(key, invalid):
    config = manifest()
    config["secret_versions"][key] = "config-secret:5"
    if invalid == "duplicate":
        config["environment"][key] = "public-value"
    else:
        config["environment"].pop(key, None)
        config["secret_versions"][key] = "config-secret:latest" if invalid == "latest" else "raw"
    with pytest.raises(ValueError):
        jobs(config, Path("plan"))


@pytest.mark.parametrize("key", ["CLICKHOUSE_HOST", "CLICKHOUSE_USER"])
def test_required_flexible_binding_cannot_be_omitted(key):
    config = manifest()
    config["environment"].pop(key)
    with pytest.raises(ValueError, match="host and user"):
        validate(config)
