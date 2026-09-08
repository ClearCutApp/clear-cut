"""Inspect an explicit private-project destination binding; apply is opt-in."""

import argparse
import hashlib
import json
import os
import re
from typing import Any

from google.cloud import firestore

from clearcut.adapters.notify.delivery import endpoint_for
from clearcut.domain.notification import binding_fingerprint, valid_binding


def apply(client: Any, binding_id: str, binding: dict[str, Any]) -> None:
    ref = client.collection("notification_bindings").document(binding_id)

    @firestore.transactional
    def write(transaction: Any) -> None:
        previous = ref.get(transaction=transaction).to_dict() or {}
        refs = [
            client.collection("project_access").document(project)
            for project in binding["project_ids"]
        ]
        scopes = [scope.get(transaction=transaction).to_dict() or {} for scope in refs]
        if any(scope.get("organization_id") != binding["organization_id"] for scope in scopes):
            raise ValueError("every explicit project must belong to the selected organization")
        if any(
            scope.get("notification_binding_id") not in {None, "", binding_id} for scope in scopes
        ):
            raise ValueError("a project already uses a different destination binding")
        if previous and binding_fingerprint(previous) != binding_fingerprint(binding):
            if binding["version"] != previous.get("version", 0) + 1:
                raise ValueError("destination changes require the next binding version")
        elif not previous and binding["version"] != 1:
            raise ValueError("a new binding starts at version one")
        transaction.set(ref, binding)
        for scope in refs:
            transaction.update(scope, {"notification_binding_id": binding_id})

    write(client.transaction())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--organization", required=True)
    parser.add_argument("--private-project", action="append", required=True)
    parser.add_argument("--binding-id", required=True)
    parser.add_argument("--version", required=True, type=int)
    parser.add_argument("--endpoint-env", default="NOTIFY_WEBHOOK_URL")
    parser.add_argument("--disabled", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    identifiers = [args.organization, args.binding_id, *args.private_project]
    if any(not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", value) for value in identifiers):
        parser.error("invalid workspace, project or binding identifier")
    endpoint = os.environ.get(args.endpoint_env, "")
    binding = {
        "organization_id": args.organization,
        "project_ids": sorted(set(args.private_project)),
        "version": args.version,
        "endpoint_env": args.endpoint_env,
        "endpoint_sha256": hashlib.sha256(endpoint.encode()).hexdigest(),
        "enabled": not args.disabled,
    }
    if not valid_binding({**binding, "enabled": True}, args.organization, args.private_project[0]):
        parser.error("invalid binding version or endpoint environment name")
    try:
        endpoint_for(binding, os.environ)
    except ValueError:
        parser.error(
            "the endpoint environment variable must contain the intended HTTPS destination"
        )
    print(
        json.dumps(
            {"binding_id": args.binding_id, "binding": binding, "apply": args.apply}, indent=2
        )
    )
    if args.apply:
        apply(firestore.Client(project=args.project), args.binding_id, binding)


if __name__ == "__main__":
    main()
