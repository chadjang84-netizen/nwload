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
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return resp.read().decode()
    except urllib.error.HTTPError as e:
        # 카메라는 4xx/5xx와 함께 SOAP Fault 본문에 실제 원인을 담아 보낸다.
        # urllib는 본문을 버리고 "HTTP Error 500" 껍데기만 남기므로, 직접 읽어 메시지에 포함시킨다.
        body = ""
        try:
            body = e.read().decode(errors="replace")
        except Exception:
            pass
        fault = (
            _text(body, "Text")          # SOAP 1.2 Fault/Reason/Text
            or _text(body, "faultstring")  # SOAP 1.1 Fault
            or " ".join(body.split())[:300]  # fault 태그가 없으면 본문 앞부분
        )
        raise RuntimeError(f"HTTP {e.code} {e.reason} — {fault or '(empty body)'}") from e


def _text(xml: str, tag: str) -> str | None:
    m = re.search(rf"<(?:[^:>]+:)?{re.escape(tag)}[^>]*>(.*?)</(?:[^:>]+:)?{re.escape(tag)}>",
                  xml, re.DOTALL)
    return m.group(1).strip() if m else None


def _all_config_tokens(xml: str) -> list[str]:
    """GetVideoEncoderConfigurationsResponse에서 각 설정의 token 속성을 문서 순서대로 추출.

    응답 형태는 `<trt:Configurations token="...">`(복수형) — token은 자식 엘리먼트가
    아니라 XML 속성이므로 _text()로는 못 뽑는다. 일부 펌웨어는 단수형 Configuration을
    echo하기도 해 둘 다 매칭한다. 단/쌍따옴표 모두 처리.
    """
    matches = re.findall(
        r"""<(?:[^:>\s]+:)?Configurations?\b[^>]*?\btoken\s*=\s*(?:"([^"]*)"|'([^']*)')""",
        xml, re.DOTALL,
    )
    return [(a or b).strip() for (a, b) in matches if (a or b).strip()]


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
        use_tls: bool = False,
        media_service_path: str = "/onvif/media",
    ) -> dict:
        scheme = "https" if use_tls else "http"
        url = f"{scheme}://{ip}:{port}{media_service_path}"
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

    def get_video_encoder_configurations(
        self,
        ip: str,
        port: int,
        username: str,
        password: str,
        use_tls: bool = False,
        media_service_path: str = "/onvif/media",
    ) -> list[str]:
        """토큰 없이 카메라의 모든 VideoEncoderConfiguration token을 조회한다."""
        scheme = "https" if use_tls else "http"
        url = f"{scheme}://{ip}:{port}{media_service_path}"
        wsse = _wsse_header(username, password)
        body = "<trt:GetVideoEncoderConfigurations/>"

        xml = _post(url, _soap(wsse, body))
        logger.debug("GetVideoEncoderConfigurations response: %s", xml[:400])
        return _all_config_tokens(xml)

    def resolve_token(
        self,
        ip: str,
        port: int,
        username: str,
        password: str,
        profile_token: str,
        use_tls: bool = False,
        media_service_path: str = "/onvif/media",
    ) -> str:
        """사용할 VideoEncoderConfiguration token을 결정한다.

        profile_token이 주어지면 그대로 사용(네트워크 호출 없음). 비어 있으면
        GetVideoEncoderConfigurations로 첫 토큰을 자동 발견한다.
        """
        if profile_token and profile_token.strip():
            return profile_token
        tokens = self.get_video_encoder_configurations(
            ip=ip, port=port, username=username, password=password,
            use_tls=use_tls, media_service_path=media_service_path,
        )
        if not tokens:
            raise RuntimeError("No VideoEncoderConfiguration found on camera — cannot auto-detect token")
        if len(tokens) > 1:
            logger.info("Camera %s:%d has %d encoder configs; using first token '%s'",
                        ip, port, len(tokens), tokens[0])
        return tokens[0]

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
        use_tls: bool = False,
        media_service_path: str = "/onvif/media",
        video_codec: str = "H264",
    ) -> bool:
        scheme = "https" if use_tls else "http"
        url = f"{scheme}://{ip}:{port}{media_service_path}"
        wsse = _wsse_header(username, password)
        width, height = resolution
        bitrate_kbps = max(1, bitrate // 1000)

        # codec별 sub-element 분기
        codec_norm = (video_codec or "H264").upper().replace(".", "")
        if codec_norm == "H265":
            encoding_tag = "H265"
            codec_block = """    <tt:H265>
      <tt:GovLength>30</tt:GovLength>
      <tt:H265Profile>Main</tt:H265Profile>
    </tt:H265>"""
        else:
            encoding_tag = "H264"
            codec_block = """    <tt:H264>
      <tt:GovLength>30</tt:GovLength>
      <tt:H264Profile>Main</tt:H264Profile>
    </tt:H264>"""

        body = f"""<trt:SetVideoEncoderConfiguration>
  <trt:Configuration token="{profile_token}">
    <tt:Name>{profile_token}</tt:Name>
    <tt:UseCount>1</tt:UseCount>
    <tt:Encoding>{encoding_tag}</tt:Encoding>
    <tt:Resolution>
      <tt:Width>{width}</tt:Width>
      <tt:Height>{height}</tt:Height>
    </tt:Resolution>
    <tt:Quality>5</tt:Quality>
    <tt:RateControl>
      <tt:FrameRateLimit>{framerate}</tt:FrameRateLimit>
      <tt:EncodingInterval>1</tt:EncodingInterval>
      <tt:BitrateLimit>{bitrate_kbps}</tt:BitrateLimit>
    </tt:RateControl>
{codec_block}
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
  <trt:ForcePersistence>false</trt:ForcePersistence>
</trt:SetVideoEncoderConfiguration>"""

        xml = _post(url, _soap(wsse, body))
        logger.debug("SetVideoEncoderConfiguration response: %s", xml[:400])

        # ONVIF returns empty body on success; fault element indicates failure
        if "Fault" in xml or "fault" in xml:
            fault_msg = _text(xml, "Text") or _text(xml, "faultstring") or "Unknown fault"
            raise RuntimeError(f"ONVIF fault: {fault_msg}")

        return True
