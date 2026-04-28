"""Reshape REST API responses into gh-CLI shape consumed by hooks/skills."""
import json


def reshape_view(rest_json):
    rest = json.loads(rest_json)
    rest["mergedAt"] = rest.pop("merged_at", None)
    rest["mergeCommit"] = {"oid": rest.pop("merge_commit_sha", None) or ""}
    rest["labels"] = [{"name": lab["name"]} for lab in rest.get("labels", [])]
    return json.dumps(rest)


def reshape_files(rest_json):
    return "\n".join(item["filename"] for item in json.loads(rest_json)) + "\n"
