"""Hardened file ingestion validation and SSRF network boundary defenses."""

from __future__ import annotations

import io
import ipaddress
import re
import socket
import urllib.parse
import zipfile
from pathlib import Path

import filetype

from src.modules.security_guardrails.domain.exceptions import (
    FileIngestionSecurityError,
)
from src.modules.security_guardrails.domain.interfaces import (
    FileValidationResult,
    IFileValidator,
    ISSRFValidator,
)

# Allowed MIME types for ingestion
_ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/zip",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/json",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/png",
    "image/jpeg",
}

# Blocked IP Networks for SSRF Defense
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),  # IPv4 loopback
    ipaddress.ip_network("10.0.0.0/8"),  # Private Class A
    ipaddress.ip_network("172.16.0.0/12"),  # Private Class B
    ipaddress.ip_network("192.168.0.0/16"),  # Private Class C
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local / Cloud Metadata (169.254.169.254)
    ipaddress.ip_network("0.0.0.0/8"),  # Current network
    ipaddress.ip_network("100.64.0.0/10"),  # Carrier-grade NAT
    ipaddress.ip_network("::1/128"),  # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),  # IPv6 Unique Local
    ipaddress.ip_network("fe80::/10"),  # IPv6 Link-local
]


class FileSecurityValidator(IFileValidator):
    """Enforces strict MIME type, zip bomb, and directory traversal security."""

    MAX_DECOMPRESSION_RATIO = 100.0  # Max ratio of uncompressed to compressed size

    def sanitize_filename(self, filename: str) -> str:
        """Strip directory traversal elements, null bytes, and shell characters."""
        # Remove path separators
        clean = Path(filename).name
        # Remove null bytes
        clean = clean.replace("\x00", "")
        # Only allow alphanumeric, dash, underscore, dot
        clean = re.sub(r"[^a-zA-Z0-9._-]", "_", clean)
        # Avoid empty or hidden dotfiles
        if not clean or clean.startswith("."):
            clean = f"upload_{clean.lstrip('.') or 'file'}"
        return clean

    def validate_file(
        self,
        file_bytes: bytes,
        filename: str,
        destination_dir: str,
        max_bytes: int = 25 * 1024 * 1024,
    ) -> FileValidationResult:
        """Inspect file magic bytes, enforce size limits, and verify path containment."""
        byte_size = len(file_bytes)
        if byte_size == 0:
            raise FileIngestionSecurityError("Empty file upload rejected.", filename=filename)

        if byte_size > max_bytes:
            raise FileIngestionSecurityError(
                f"File size ({byte_size} bytes) exceeds maximum allowable limit ({max_bytes} bytes).",
                filename=filename,
            )

        # Detect MIME type via magic bytes
        kind = filetype.guess(file_bytes)
        if kind is not None:
            mime = kind.mime
        else:
            # Fallback for plain text, markdown, CSV, json
            try:
                file_bytes.decode("utf-8")
                # Infer from extension safely
                ext = Path(filename).suffix.lower()
                if ext == ".md":
                    mime = "text/markdown"
                elif ext == ".csv":
                    mime = "text/csv"
                elif ext == ".json":
                    mime = "application/json"
                else:
                    mime = "text/plain"
            except UnicodeDecodeError as exc:
                raise FileIngestionSecurityError(
                    "Unrecognized binary file format or corrupted text.", filename=filename
                ) from exc

        if mime not in _ALLOWED_MIME_TYPES:
            raise FileIngestionSecurityError(
                f"Disallowed MIME type '{mime}'. Allowed types: {', '.join(sorted(_ALLOWED_MIME_TYPES))}",
                filename=filename,
            )

        # Check for zip bomb if uploaded as zip or docx
        if mime in (
            "application/zip",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ):
            try:
                with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                    total_uncompressed = 0
                    for info in zf.infolist():
                        total_uncompressed += info.file_size
                        if byte_size > 0:
                            ratio = total_uncompressed / byte_size
                            if ratio > self.MAX_DECOMPRESSION_RATIO:
                                raise FileIngestionSecurityError(
                                    f"Potential Zip Bomb detected. Decompression ratio exceeds {self.MAX_DECOMPRESSION_RATIO}:1",
                                    filename=filename,
                                )
            except zipfile.BadZipFile as exc:
                raise FileIngestionSecurityError(
                    f"Corrupted or invalid zip archive: {exc}", filename=filename
                ) from exc

        # Verify path containment inside SAFE_UPLOAD_DIR
        safe_dir = Path(destination_dir).resolve()
        safe_dir.mkdir(parents=True, exist_ok=True)

        clean_name = self.sanitize_filename(filename)
        canonical_target = (safe_dir / clean_name).resolve()

        if not canonical_target.is_relative_to(safe_dir):
            raise FileIngestionSecurityError(
                "Path traversal attempt detected. File path escapes designated safe upload directory.",
                filename=filename,
            )

        return FileValidationResult(
            is_valid=True,
            mime_type=mime,
            byte_size=byte_size,
            canonical_path=str(canonical_target),
        )


class SSRFValidator(ISSRFValidator):
    """Enforces strict outbound network URL validation and blocks SSRF attacks."""

    ALLOWED_SCHEMES = ("http", "https")

    def validate_url(self, url: str) -> tuple[bool, str | None]:
        """Validate URL scheme and ensure target IP does not resolve to private or metadata addresses."""
        if not url:
            return False, "Empty URL provided."

        try:
            parsed = urllib.parse.urlparse(url)
        except Exception as exc:
            return False, f"Invalid URL format: {exc}"

        if parsed.scheme.lower() not in self.ALLOWED_SCHEMES:
            return False, f"Scheme '{parsed.scheme}' forbidden. Only HTTP/HTTPS allowed."

        hostname = parsed.hostname
        if not hostname:
            return False, "URL contains no valid host."

        # Reject common metadata hostnames
        normalized_host = hostname.lower()
        if normalized_host in ("metadata.google.internal", "instance-data", "localhost"):
            return False, f"Access to host '{hostname}' is blocked by security policy."

        # Resolve DNS addresses
        try:
            addr_info = socket.getaddrinfo(
                hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
            )
        except socket.gaierror as exc:
            return False, f"Unable to resolve DNS for host '{hostname}': {exc}"

        for entry in addr_info:
            ip_str = entry[4][0]
            try:
                ip_obj = ipaddress.ip_address(ip_str)
                for blocked_net in _BLOCKED_NETWORKS:
                    if ip_obj in blocked_net:
                        return (
                            False,
                            f"Access to private/loopback/metadata IP '{ip_str}' is blocked.",
                        )
            except ValueError:
                continue

        return True, None
