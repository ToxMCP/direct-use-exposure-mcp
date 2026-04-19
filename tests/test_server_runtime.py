from __future__ import annotations

import asyncio

from exposure_scenario_mcp import server as server_module


def _run(coro):
    return asyncio.run(coro)


def test_runtime_provider_reuses_lazy_state_and_lifespan_startup(monkeypatch) -> None:
    init_count = 0
    original_factory = server_module.build_server_runtime_state

    def counting_factory():
        nonlocal init_count
        init_count += 1
        return original_factory()

    monkeypatch.setattr(server_module, "build_server_runtime_state", counting_factory)
    server = server_module.create_mcp_server()

    direct_result = _run(server.call_tool("exposure_run_verification_checks", {}))
    assert not direct_result.isError
    assert init_count == 1

    async def exercise_lifespan() -> None:
        provider = server._server_runtime_provider
        cached_state = provider.get_runtime_state()
        assert init_count == 1

        async with server._mcp_server.lifespan(server._mcp_server) as lifespan_state:
            assert lifespan_state is cached_state
            assert init_count == 1

            managed_result = await server.call_tool("exposure_run_verification_checks", {})
            assert not managed_result.isError
            assert init_count == 1

        assert provider._runtime_state is None

    _run(exercise_lifespan())

    post_shutdown_result = _run(server.call_tool("exposure_run_verification_checks", {}))
    assert not post_shutdown_result.isError
    assert init_count == 2
