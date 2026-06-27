"""Verizon Router API handler."""

import asyncio
import hashlib
import json
import logging
import re
import ssl
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

_JS_STRING_PATTERN = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', flags=re.DOTALL)
_INNER_STRING_PATTERN = re.compile(r'\\.|"', flags=re.DOTALL)


def _inner_repl(match: re.Match) -> str:
    g = match.group(0)
    if g == "\\'":
        return "'"
    if g == '"':
        return '\\"'
    return g


def _replacer(match: re.Match) -> str:
    s = match.group(0)
    if s.startswith('"'):
        return s
    new_inner = _INNER_STRING_PATTERN.sub(_inner_repl, s[1:-1])
    return '"' + new_inner + '"'


class VerizonRouterAPI:
    """Handle Verizon Router API communication."""

    def __init__(self, router_url: str, username: str, password: str):
        """Initialize the API handler."""
        self.router_url = router_url
        self.username = username
        self.password = password
        # Single SSL context created via the public API and reused for every
        # connection.  ssl._create_unverified_context() is a private helper
        # that may disappear; the two lines below are the documented way to
        # achieve the same result.
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE

    def _arc_md5(self, text: str) -> str:
        """Verizon's custom ArcMD5 hash: MD5 -> SHA512."""
        md5_hash = hashlib.md5(text.encode()).hexdigest()
        sha512_hash = hashlib.sha512(md5_hash.encode("ascii")).hexdigest()
        return sha512_hash

    def _login_encode(self, password: str, token: str) -> str:
        """Encode password with token: SHA512(token + ArcMD5(password))."""
        arc_md5_result = self._arc_md5(password)
        combined = token + arc_md5_result
        final_hash = hashlib.sha512(combined.encode("ascii")).hexdigest()
        return final_hash

    def _hash_username(self, username: str) -> str:
        """Hash username using ArcMD5."""
        return self._arc_md5(username)

    def _convert_js_to_json(self, value_str: str) -> str:
        """Convert JavaScript string literals to JSON-compatible double quotes.

        The router returns data as JavaScript with single-quoted strings.
        A simple regex replacement (e.g. s/'([^']*)'/"\\1"/) breaks on
        apostrophes inside double-quoted strings and on escaped quotes inside
        single-quoted strings.  This method uses regular expressions to find
        and replace strings accurately:

        - Double-quoted strings pass through completely unchanged (preserving
          any apostrophes they contain).
        - Single-quoted strings are converted to double-quoted, with:
            - \\' (escaped single quote) → bare '
            - bare " inside the string → \\"
        """
        return _JS_STRING_PATTERN.sub(_replacer, value_str)

    def _parse_js_value(self, js_content: str, variable_name: str) -> Any:
        """Parse JavaScript variable values from router response."""
        rod_pattern = rf'addROD\("{variable_name}",\s*(.+?)\s*\);'
        match = re.search(rod_pattern, js_content, re.DOTALL)

        if not match:
            return None

        try:
            value_str = match.group(1).strip()

            # For complex objects/arrays, find the matching closing bracket
            # by walking character-by-character.  string_char tracks whether
            # we are inside a string and, if so, which quote character opened
            # it.  This prevents mismatched quotes (e.g. an apostrophe inside
            # a double-quoted string) from confusing the bracket counter.
            if value_str.startswith("{") or value_str.startswith("["):
                bracket_count = 0
                brace_count = 0
                end_pos = 0
                string_char = None  # None = not in string; '"' or "'" = in string
                escape_next = False

                for i, char in enumerate(value_str):
                    if escape_next:
                        escape_next = False
                        continue
                    if char == "\\":
                        escape_next = True
                        continue
                    if string_char is not None:
                        # Inside a string — only the matching quote closes it
                        if char == string_char:
                            string_char = None
                        continue
                    # Not inside a string
                    if char in ('"', "'"):
                        string_char = char
                        continue

                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                    elif char == "[":
                        bracket_count += 1
                    elif char == "]":
                        bracket_count -= 1

                    if brace_count == 0 and bracket_count == 0:
                        end_pos = i + 1
                        break

                if end_pos > 0:
                    value_str = value_str[:end_pos]

            # Convert JS single-quoted strings to JSON double-quoted strings
            value_str = self._convert_js_to_json(value_str)
            # Remove trailing commas before closing brackets (invalid in JSON)
            value_str = re.sub(r",(\s*[}\]])", r"\1", value_str)

            return json.loads(value_str)
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.debug("Error parsing %s: %s", variable_name, e)
            return None

    async def _get_login_token(self, session: aiohttp.ClientSession) -> str | None:
        """Get login token from router."""
        try:
            async with session.get(
                f"{self.router_url}/loginStatus.cgi",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                _LOGGER.debug("Token request status: %s", response.status)
                if response.status == 200:
                    text = await response.text()
                    _LOGGER.debug("Token response text: %s", text[:200])

                    try:
                        data = json.loads(text)
                    except json.JSONDecodeError as e:
                        _LOGGER.error("Failed to parse token response as JSON: %s", e)
                        return None

                    token = data.get("loginToken")
                    if token:
                        _LOGGER.debug("Successfully retrieved login token")
                        return token

                    _LOGGER.error("No loginToken in response: %s", data)
                    return None

                _LOGGER.error("Bad status getting token: %s", response.status)
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout getting login token")
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error("Error getting login token: %s", e)
        return None

    async def _login(self, session: aiohttp.ClientSession, token: str) -> bool:
        """Login to router."""
        try:
            username_hash = self._hash_username(self.username)
            password_hash = self._login_encode(self.password, token)

            _LOGGER.debug("Login attempt with username: %s", self.username)

            login_data = {
                "luci_username": username_hash,
                "luci_password": password_hash,
                "luci_view": "Desktop",
                "luci_token": token,
                "luci_keep_login": "0",
            }

            headers = {
                "Origin": self.router_url,
                "Referer": f"{self.router_url}/",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }

            async with session.post(
                f"{self.router_url}/login.cgi",
                data=login_data,
                headers=headers,
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                _LOGGER.debug("Login response status: %s", response.status)

                if response.status == 302:
                    # Try Set-Cookie header first
                    if "Set-Cookie" in response.headers:
                        set_cookie = response.headers.get("Set-Cookie", "")
                        if "sysauth=" in set_cookie:
                            match = re.search(r"sysauth=([^;]+)", set_cookie)
                            if match and match.group(1):
                                _LOGGER.info("Login successful")
                                return True

                    # Fallback: check cookie jar
                    cookies = session.cookie_jar.filter_cookies(self.router_url)
                    for cookie in cookies.values():
                        if cookie.key == "sysauth" and cookie.value:
                            _LOGGER.info("Login successful")
                            return True

                    _LOGGER.error("Login failed - no sysauth cookie found")
                else:
                    _LOGGER.error(
                        "Login failed - unexpected status: %s", response.status
                    )

        except asyncio.TimeoutError:
            _LOGGER.error("Login timeout")
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error("Login error: %s", e)
        return False

    async def test_connection(self) -> bool:
        """Test if we can connect to the router."""
        _LOGGER.debug("Testing connection to %s", self.router_url)

        # SSL context is set on the connector; individual requests inherit it
        # automatically — no need to pass ssl= on each call.
        connector = aiohttp.TCPConnector(ssl=self._ssl_context)
        cookie_jar = aiohttp.CookieJar(unsafe=True)
        timeout = aiohttp.ClientTimeout(total=30)

        try:
            async with aiohttp.ClientSession(
                connector=connector, cookie_jar=cookie_jar, timeout=timeout
            ) as session:
                token = await self._get_login_token(session)
                if not token:
                    _LOGGER.error("Failed to get login token")
                    return False

                login_result = await self._login(session, token)
                if not login_result:
                    _LOGGER.error("Login failed - check credentials")

                return login_result
        except aiohttp.ClientError as e:
            _LOGGER.error("Connection error: %s", e)
            return False
        except asyncio.TimeoutError:
            _LOGGER.error("Connection timeout")
            return False
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error("Connection test failed: %s", e)
            return False
        finally:
            # Ensure connector is properly closed
            if not connector.closed:
                await connector.close()

    async def fetch_router_data(self) -> dict[str, Any]:
        """Fetch all router data."""
        connector = aiohttp.TCPConnector(ssl=self._ssl_context)
        cookie_jar = aiohttp.CookieJar(unsafe=True)
        timeout = aiohttp.ClientTimeout(total=60)

        try:
            async with aiohttp.ClientSession(
                connector=connector, cookie_jar=cookie_jar, timeout=timeout
            ) as session:
                # Login
                token = await self._get_login_token(session)
                if not token:
                    raise Exception(
                        "Could not get login token"
                    )  # pylint: disable=broad-exception-raised

                if not await self._login(session, token):
                    raise Exception(
                        "Login failed"
                    )  # pylint: disable=broad-exception-raised

                # Fetch data files
                headers = {"Referer": f"{self.router_url}/"}

                # Get cgi_basic.js
                async with session.get(
                    f"{self.router_url}/cgi/cgi_basic.js",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status != 200:
                        raise Exception(  # pylint: disable=broad-exception-raised
                            f"Failed to fetch cgi_basic.js: {response.status}"
                        )
                    basic_content = await response.text()

                # Get cgi_owl.js (optional — not all routers expose this endpoint)
                owl_content = None
                try:
                    async with session.get(
                        f"{self.router_url}/cgi/cgi_owl.js",
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as response:
                        if response.status == 200:
                            owl_content = await response.text()
                except Exception as e:  # pylint: disable=broad-except
                    _LOGGER.debug("Could not fetch cgi_owl.js: %s", e)

                return await self._parse_data(basic_content, owl_content)
        finally:
            # Ensure connector is properly closed
            if not connector.closed:
                await connector.close()

    async def _parse_data(
        self, basic_content: str, owl_content: str | None
    ) -> dict[str, Any]:
        """Parse router data into structured format."""
        data = {}

        # Parse topology
        topology = self._parse_js_value(basic_content, "dump_toplogy_map_info")
        if topology and "nodes" in topology:
            data["topology"] = topology

        # Parse known devices
        known_devices = self._parse_js_value(basic_content, "known_device_list")
        if not known_devices and owl_content:
            known_devices = self._parse_js_value(owl_content, "known_device_list")
        if known_devices:
            data["known_devices"] = known_devices

        # Parse station info
        station_info = self._parse_js_value(basic_content, "dump_toplogy_station_info")
        if not station_info and owl_content:
            station_info = self._parse_js_value(
                owl_content, "dump_toplogy_station_info"
            )
        if station_info:
            data["station_info"] = station_info

        # Parse router name
        router_name = self._parse_js_value(basic_content, "router_name")
        if router_name:
            data["router_name"] = router_name

        # Parse hardware model
        hardware_model = self._parse_js_value(basic_content, "hardware_model")
        if hardware_model:
            data["hardware_model"] = hardware_model

        return data
