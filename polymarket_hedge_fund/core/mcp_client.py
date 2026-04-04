"""
MCP Client — Connects to the Polymarket MCP Server.
Sends tool calls via MCP protocol (stdio or SSE).
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class MCPConfig:
    """Configuration for connecting to the Polymarket MCP Server."""
    python_path: str = ""          # Path to venv python
    server_module: str = "polymarket_mcp.server"
    server_cwd: str = ""           # Path to polymarket-mcp-server repo
    polygon_private_key: str = ""  # Without 0x prefix
    polygon_address: str = ""      # With 0x prefix

    def validate(self) -> list[str]:
        errors = []
        if not self.python_path:
            errors.append("python_path is required (path to venv python)")
        if not self.server_cwd:
            errors.append("server_cwd is required (path to polymarket-mcp-server)")
        if not self.polygon_private_key:
            errors.append("polygon_private_key is required")
        if not self.polygon_address:
            errors.append("polygon_address is required")
        if self.polygon_private_key.startswith("0x"):
            errors.append("polygon_private_key must NOT start with 0x")
        if not self.polygon_address.startswith("0x"):
            errors.append("polygon_address MUST start with 0x")
        return errors


class MCPClient:
    """
    MCP Client that communicates with the Polymarket MCP Server
    via stdio (JSON-RPC over stdin/stdout).
    """

    def __init__(self, config: MCPConfig):
        self.config = config
        self._process: Optional[subprocess.Popen] = None
        self._request_id: int = 0
        self._connected: bool = False

    async def connect(self) -> None:
        """Start the MCP server process and establish connection."""
        errors = self.config.validate()
        if errors:
            raise ValueError(f"Invalid MCP config: {'; '.join(errors)}")

        # Minimal env — only pass what the MCP server needs, not the entire parent env
        import os as _os
        minimal_env = {
            "PATH": _os.environ.get("PATH", "") + _os.pathsep + str(Path(self.config.python_path).parent),
            "HOME": _os.environ.get("HOME", ""),
            "POLYGON_PRIVATE_KEY": self.config.polygon_private_key,
            "POLYGON_ADDRESS": self.config.polygon_address,
            "PYTHONPATH": self.config.server_cwd,
        }

        self._process = subprocess.Popen(
            [self.config.python_path, "-m", self.config.server_module],
            cwd=self.config.server_cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=minimal_env,
        )

        # Send initialize request
        response = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "polymarket-hedge-fund", "version": "3.0.0"},
        })

        if response and "result" in response:
            self._connected = True
            logger.info("✅ Connected to Polymarket MCP Server")

            # Send initialized notification
            await self._send_notification("notifications/initialized", {})
        else:
            raise ConnectionError(f"Failed to initialize MCP: {response}")

    async def disconnect(self) -> None:
        """Shut down the MCP server process."""
        if self._process:
            self._process.terminate()
            self._process.wait(timeout=5)
            self._connected = False
            logger.info("🔌 Disconnected from MCP Server")

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict:
        """
        Call an MCP tool and return the result.
        This is the main method used by all API implementations.
        """
        if not self._connected:
            raise ConnectionError("Not connected to MCP Server")

        response = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })

        if response and "result" in response:
            return response["result"]
        elif response and "error" in response:
            error = response["error"]
            raise RuntimeError(
                f"MCP tool error [{error.get('code')}]: {error.get('message')}"
            )
        else:
            raise RuntimeError(f"Unexpected MCP response: {response}")

    async def list_tools(self) -> list[dict]:
        """List all available tools from the MCP server."""
        response = await self._send_request("tools/list", {})
        if response and "result" in response:
            return response["result"].get("tools", [])
        return []

    async def _send_request(self, method: str, params: dict) -> Optional[dict]:
        """Send a JSON-RPC request to the MCP server."""
        self._request_id += 1
        message = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }
        return await self._send_message(message)

    async def _send_notification(self, method: str, params: dict) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        await self._write_message(message)

    async def _send_message(self, message: dict) -> Optional[dict]:
        """Write a message and read the response."""
        await self._write_message(message)
        return await self._read_response()

    async def _write_message(self, message: dict) -> None:
        """Write a JSON-RPC message to the server's stdin."""
        if not self._process or not self._process.stdin:
            raise ConnectionError("MCP process not running")

        content_bytes = json.dumps(message).encode("utf-8")
        header = f"Content-Length: {len(content_bytes)}\r\n\r\n"
        data = header.encode("ascii") + content_bytes

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._process.stdin.write, data)
        await loop.run_in_executor(None, self._process.stdin.flush)

    async def _read_response(self) -> Optional[dict]:
        """Read a JSON-RPC response from the server's stdout."""
        if not self._process or not self._process.stdout:
            raise ConnectionError("MCP process not running")

        loop = asyncio.get_event_loop()

        # Read Content-Length header
        header = b""
        while True:
            byte = await loop.run_in_executor(
                None, self._process.stdout.read, 1
            )
            if not byte:
                return None
            header += byte
            if header.endswith(b"\r\n\r\n"):
                break

        # Parse content length
        header_str = header.decode()
        content_length = 0
        for line in header_str.split("\r\n"):
            if line.startswith("Content-Length:"):
                content_length = int(line.split(":")[1].strip())
                break

        if content_length == 0:
            return None

        # Read content
        content = await loop.run_in_executor(
            None, self._process.stdout.read, content_length
        )
        return json.loads(content.decode())
