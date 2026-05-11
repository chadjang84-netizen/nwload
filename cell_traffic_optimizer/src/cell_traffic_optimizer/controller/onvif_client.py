"""
Real ONVIF HTTP/SOAP client.

ONVIF Media service (WSDL ver 2.x) — GetVideoEncoderConfiguration /
SetVideoEncoderConfiguration over plain HTTP with WS-UsernameToken digest auth.

No third-party library required: uses stdlib urllib + hashlib only.
"""
from __future__ import annotations

import hashlib
import logging
import re
import urllib.error
import urllib.request
from base64 import b64encode
from datetime import datetime, timezone
from os import urandom

logger = logging.getLogger(__name__)

_TIMEOUT = 5  # seconds per request


# ── WS-Security UsernameToken (digest) ────────────────────────────────────────

def _wsse_header(username: str, password: str) -> str:
    nonce_bytes = urandom(16)
    nonce_b64 = b64encode(nonce_bytes).decode()
    created = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    digest_raw = nonce_bytes + created.encode() + password.encode()
    digest_b64 = b64encode(hashlib.sha1(digest_raw).digest()).decode()

    return f"""<wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
                              xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
  <wsse:UsernameToken>
    <wsse:Username>{username}</wsse:Username>
    <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest">{digest_b64}</wsse:Password>
    <wsse:Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">{nonce_b64}</wsse:Nonce>
    <wsu:Created>{created}</wsu:Created>
  </wsse:UsernameToken>
</wsse:Security>"""


# ── SOAP envelope helpers ──────────────────────────────────────────────────────

def _soap(wsse: str, body: str) -> bytes:
    envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:trt="http://www.onvif.org/ver10/media/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Header>{wsse}</s:Header>
  <s:Body>{body}</s:Body>
</s:Envelope>"""
    return envelope.encode()


def _post(url: str, payload: bytes) -> str:
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/soap+xml; charset=utf-8",
            "Content-Length": str(len(payload)),
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return resp.read().decode()


def _text(xml: str, tag: str) -> str | None:
    m = re.search(rf"<(?:[^:>]+:)?{re.escape(tag)}[^>]*>(.*?)</(?:[^:>]+:)?{re.escape(tag)}>",
                  xml, re.DOTALL)
    return m.group(1).strip() if m else None


# ── Public ONVIF client ────────────────────────────────────────────────────────

class OnvifClient:
    """Concrete ONVIF client — satisfies the ONVIFClient Protocol."""

    def get_video_encoder_configuration(
        self,
        ip: str,
        port: int,
        username: str,
        password: str,
        profile_token: str,
    ) -> dict:
        url = f"http://{ip}:{port}/onvif/media"
        wsse = _wsse_header(username, password)
        body = f"""<trt:GetVideoEncoderConfiguration>
  <trt:ConfigurationToken>{profile_token}</trt:ConfigurationToken>
</trt:GetVideoEncoderConfiguration>"""

        xml = _post(url, _soap(wsse, body))
        logger.debug("GetVideoEncoderConfiguration response: %s", xml[:400])

        bitrate   = int(_text(xml, "BitrateLimit") or _text(xml, "Bitrate") or "4096")
        framerate = int(_text(xml, "FrameRateLimit") or _text(xml, "FrameRate") or "30")
        width     = int(_text(xml, "Width") or "1920")
        height    = int(_text(xml, "Height") or "1080")

        # ONVIF reports bitrate in kbps — convert to bps for internal consistency
        return {"bitrate": bitrate * 1000, "framerate": framerate, "resolution": (width, height)}

    def set_video_encoder_configuration(
        self,
        ip: str,
        port: int,
        username: str,
        password: str,
        profile_token: str,
        bitrate: int,
        framerate: int,
        resolution: tuple,
    ) -> bool:
        url = f"http://{ip}:{port}/onvif/media"
        wsse = _wsse_header(username, password)
        width, height = resolution
        bitrate_kbps = max(1, bitrate // 1000)

        body = f"""<trt:SetVideoEncoderConfiguration>
  <trt:Configuration token="{profile_token}">
    <tt:Name>{profile_token}</tt:Name>
    <tt:UseCount>1</tt:UseCount>
    <tt:Encoding>H264</tt:Encoding>
    <tt:Resolution>
      <tt:Width>{width}</tt:Width>
      <tt:Height>{height}</tt:Height>
    </tt:Resolution>
    <tt:FrameRateLimit>{framerate}</tt:FrameRateLimit>
    <tt:EncodingInterval>1</tt:EncodingInterval>
    <tt:BitrateLimit>{bitrate_kbps}</tt:BitrateLimit>
    <tt:H264>
      <tt:GovLength>30</tt:GovLength>
      <tt:H264Profile>Main</tt:H264Profile>
    </tt:H264>
    <tt:Multicast>
      <tt:Address>
        <tt:Type>IPv4</tt:Type>
        <tt:IPv4Address>0.0.0.0</tt:IPv4Address>
      </tt:Address>
      <tt:Port>0</tt:Port>
      <tt:TTL>1</tt:TTL>
      <tt:AutoStart>false</tt:AutoStart>
    </tt:Multicast>
    <tt:SessionTimeout>PT60S</tt:SessionTimeout>
  </trt:Configuration>
  <trt:ForcePersistence>true</trt:ForcePersistence>
</trt:SetVideoEncoderConfiguration>"""

        xml = _post(url, _soap(wsse, body))
        logger.debug("SetVideoEncoderConfiguration response: %s", xml[:400])

        # ONVIF returns empty body on success; fault element indicates failure
        if "Fault" in xml or "fault" in xml:
            fault_msg = _text(xml, "Text") or _text(xml, "faultstring") or "Unknown fault"
            raise RuntimeError(f"ONVIF fault: {fault_msg}")

        return True
