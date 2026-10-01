"""Collect contracts and scientific results through an isolated SDK1 or SDK2 client."""

from __future__ import annotations

import argparse
import json
from contextlib import asynccontextmanager, suppress
from importlib.metadata import version
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def stable(value):
    """Remove per-call timestamps; retain scientific data and content-derived identities."""
    if isinstance(value, dict):
        return {
            key: stable(item)
            for key, item in value.items()
            if key not in {"generated_at", "generatedAt", "executed_at", "executedAt", "requestId"}
        }
    if isinstance(value, list):
        return [stable(item) for item in value]
    return value


@asynccontextmanager
async def connection(args):
    server = args.url or StdioServerParameters(
        command=args.server_python,
        args=[args.deterministic_launcher]
        if args.deterministic_launcher
        else ["-m", "exposure_scenario_mcp"],
        env={"PYTHONPATH": str(Path(args.server_root) / "src")} if args.server_root else {},
    )
    if args.modern:
        from mcp import Client

        async with Client(server) as client:
            yield client, client.protocol_version
    else:
        if args.url:
            from mcp.client.streamable_http import streamablehttp_client

            transport = streamablehttp_client(args.url)
        else:
            transport = stdio_client(server)
        async with transport as streams, ClientSession(streams[0], streams[1]) as session:
            initialized = await session.initialize()
            yield session, initialized.model_dump(mode="json", by_alias=True)["protocolVersion"]


async def collect(args):
    fixture = json.loads(Path(args.fixtures).read_text())
    async with connection(args) as (client, protocol):
        catalog = {}
        for key, method, wire_key in [
            ("tools", client.list_tools, "tools"),
            ("resources", client.list_resources, "resources"),
            ("templates", client.list_resource_templates, "resourceTemplates"),
            ("prompts", client.list_prompts, "prompts"),
        ]:
            response = await method()
            catalog[key] = response.model_dump(mode="json", by_alias=True, exclude_none=True)[
                wire_key
            ]
        results = {}
        for call in fixture["calls"]:
            response = await client.call_tool(call["name"], call["arguments"])
            wire = response.model_dump(mode="json", by_alias=True, exclude_none=True)
            if wire.get("isError", False) != call.get("isError", False):
                raise AssertionError((call["name"], wire))
            results[call["label"]] = stable(wire)
        for uri in fixture["resources"]:
            response = await client.read_resource(uri)
            wire = response.model_dump(mode="json", by_alias=True, exclude_none=True)
            for item in wire["contents"]:
                if "text" in item:
                    with suppress(json.JSONDecodeError):
                        item["text"] = stable(json.loads(item["text"]))
            results[uri] = stable(wire)
        prompt = await client.get_prompt("exposure_pbpk_handoff_checklist", {"route": "oral"})
        results["prompt"] = prompt.model_dump(mode="json", by_alias=True, exclude_none=True)
        return {
            "clientSDK": version("mcp"),
            "protocol": protocol,
            "catalog": catalog,
            "results": results,
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-python", required=True)
    parser.add_argument("--server-root")
    parser.add_argument("--deterministic-launcher")
    parser.add_argument("--url")
    parser.add_argument("--modern", action="store_true")
    parser.add_argument("--fixtures", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = anyio.run(collect, args)
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "clientSDK": report["clientSDK"],
                "protocol": report["protocol"],
                "catalog": {key: len(items) for key, items in report["catalog"].items()},
                "workflows": len(report["results"]),
            }
        )
    )


if __name__ == "__main__":
    main()
