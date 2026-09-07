import json
from pathlib import Path


WORKFLOW_PATH = (
    Path(__file__).resolve().parent.parent
    / "automation"
    / "route-support-ticket-by-priority.json"
)


def test_n8n_workflow_uses_internal_api_without_environment_secret_access() -> None:
    workflow = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    nodes = {node["name"]: node for node in workflow["nodes"]}
    api_node = nodes["Create and triage ticket"]

    assert api_node["parameters"]["url"] == "http://api:8002/tickets"
    assert "$env" not in json.dumps(api_node)


def test_n8n_workflow_keeps_both_routing_responses() -> None:
    workflow = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    nodes = {node["name"]: node for node in workflow["nodes"]}

    assert nodes["Urgent ticket accepted"]["parameters"]["options"]["responseCode"] == 202
    assert nodes["Standard ticket accepted"]["parameters"]["options"]["responseCode"] == 201
