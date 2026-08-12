"""Tests for DUCKLAKE_MCP_HOST / DUCKLAKE_MCP_PORT wiring into FastMCP.

Importing ori_ducklake_mcp.server never opens a network connection (the
DuckLake ATTACH happens lazily on first tool call, not at import time), so
these tests are safe to run offline.
"""

from __future__ import annotations

import importlib
import os
import unittest


class TestHostPortConfig(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = {
            key: os.environ.pop(key, None)
            for key in ("DUCKLAKE_MCP_HOST", "DUCKLAKE_MCP_PORT")
        }

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_defaults_bind_all_interfaces_on_port_8000(self) -> None:
        from ori_ducklake_mcp import server

        importlib.reload(server)
        self.assertEqual(server.MCP_HOST, "0.0.0.0")
        self.assertEqual(server.MCP_PORT, 8000)
        self.assertEqual(server.mcp.settings.host, "0.0.0.0")
        self.assertEqual(server.mcp.settings.port, 8000)

    def test_env_vars_override_host_and_port(self) -> None:
        os.environ["DUCKLAKE_MCP_HOST"] = "192.168.1.5"
        os.environ["DUCKLAKE_MCP_PORT"] = "9001"

        from ori_ducklake_mcp import server

        importlib.reload(server)
        self.assertEqual(server.MCP_HOST, "192.168.1.5")
        self.assertEqual(server.MCP_PORT, 9001)
        self.assertEqual(server.mcp.settings.host, "192.168.1.5")
        self.assertEqual(server.mcp.settings.port, 9001)


if __name__ == "__main__":
    unittest.main()
