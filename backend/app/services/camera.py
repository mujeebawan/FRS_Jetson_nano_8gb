"""
Camera service for Hikvision camera integration.
Supports ISAPI for smart features and motion detection events.
"""

import logging
import httpx
from typing import Optional, Dict, Any
from dataclasses import dataclass
import asyncio

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class CameraInfo:
    """Camera device information"""
    model: str
    serial_number: str
    firmware: str
    mac_address: str


@dataclass
class MotionEvent:
    """Motion detection event from camera"""
    timestamp: str
    channel_id: int
    event_type: str
    active: bool


class CameraService:
    """
    Hikvision camera integration via ISAPI.
    Provides motion detection events to reduce unnecessary processing.
    """

    def __init__(
        self,
        ip: str = None,
        username: str = None,
        password: str = None
    ):
        self.ip = ip or settings.camera_ip
        self.username = username or settings.camera_username
        self.password = password or settings.camera_password
        self.base_url = f"http://{self.ip}"

        self._client: Optional[httpx.AsyncClient] = None
        self._motion_active = False
        self._last_motion_time = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with digest auth."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                auth=httpx.DigestAuth(self.username, self.password),
                timeout=10.0
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_device_info(self) -> Optional[CameraInfo]:
        """Get camera device information."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/ISAPI/System/deviceInfo")

            if response.status_code == 200:
                # Parse XML response
                import xml.etree.ElementTree as ET
                root = ET.fromstring(response.text)
                ns = {'hik': 'http://www.hikvision.com/ver20/XMLSchema'}

                return CameraInfo(
                    model=root.findtext('.//hik:model', '', ns),
                    serial_number=root.findtext('.//hik:serialNumber', '', ns),
                    firmware=root.findtext('.//hik:firmwareVersion', '', ns),
                    mac_address=root.findtext('.//hik:macAddress', '', ns)
                )

        except Exception as e:
            logger.error(f"Failed to get device info: {e}")

        return None

    async def get_motion_status(self) -> bool:
        """Check if motion is currently detected."""
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.base_url}/ISAPI/Event/triggers/VMD-1/status"
            )

            if response.status_code == 200:
                return '<eventState>active</eventState>' in response.text.lower()

        except Exception as e:
            logger.debug(f"Motion status check failed: {e}")

        return False

    async def subscribe_motion_events(self, callback) -> None:
        """
        Subscribe to motion detection events via alertStream.
        This is a long-polling endpoint that streams events.

        Args:
            callback: Async function to call when motion detected
        """
        try:
            client = await self._get_client()
            url = f"{self.base_url}/ISAPI/Event/notification/alertStream"

            async with client.stream('GET', url) as response:
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk

                    # Look for complete event notifications
                    while '<EventNotificationAlert' in buffer and '</EventNotificationAlert>' in buffer:
                        start = buffer.find('<EventNotificationAlert')
                        end = buffer.find('</EventNotificationAlert>') + len('</EventNotificationAlert>')

                        event_xml = buffer[start:end]
                        buffer = buffer[end:]

                        # Parse event
                        if 'VMD' in event_xml or 'fielddetection' in event_xml.lower():
                            is_active = 'active' in event_xml.lower()
                            await callback(MotionEvent(
                                timestamp=self._extract_xml_value(event_xml, 'dateTime'),
                                channel_id=1,
                                event_type='motion',
                                active=is_active
                            ))

        except Exception as e:
            logger.error(f"Motion event subscription failed: {e}")

    def _extract_xml_value(self, xml: str, tag: str) -> str:
        """Extract value from XML tag."""
        import re
        match = re.search(f'<{tag}>([^<]*)</{tag}>', xml)
        return match.group(1) if match else ""

    async def capture_snapshot(self) -> Optional[bytes]:
        """Capture a JPEG snapshot from camera."""
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.base_url}/ISAPI/Streaming/channels/101/picture"
            )

            if response.status_code == 200:
                return response.content

        except Exception as e:
            logger.error(f"Snapshot capture failed: {e}")

        return None

    async def get_stream_info(self, channel: int = 101) -> Dict[str, Any]:
        """Get streaming channel information."""
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.base_url}/ISAPI/Streaming/channels/{channel}"
            )

            if response.status_code == 200:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(response.text)
                ns = {'hik': 'http://www.hikvision.com/ver20/XMLSchema'}

                video = root.find('.//hik:Video', ns)
                if video:
                    return {
                        'width': int(video.findtext('hik:videoResolutionWidth', '0', ns)),
                        'height': int(video.findtext('hik:videoResolutionHeight', '0', ns)),
                        'codec': video.findtext('hik:videoCodecType', '', ns),
                        'bitrate': int(video.findtext('hik:constantBitRate', '0', ns)),
                    }

        except Exception as e:
            logger.error(f"Failed to get stream info: {e}")

        return {}

    def get_rtsp_url(self, channel: str = "103") -> str:
        """
        Get RTSP URL for specified channel.

        Args:
            channel: "101" (main), "102" (sub), "103" (third/720p)

        Returns:
            RTSP URL string
        """
        return (
            f"rtsp://{self.username}:{self.password}@"
            f"{self.ip}:554/Streaming/Channels/{channel}"
        )

    @property
    def is_motion_active(self) -> bool:
        """Check cached motion status."""
        return self._motion_active

    async def ptz_zoom(self, action: str = "stop", speed: int = 50) -> bool:
        """
        Control camera zoom via PTZ continuous.

        Args:
            action: "in", "out", or "stop"
            speed: Zoom speed 1-100 (default 50)

        Returns:
            Success status
        """
        try:
            client = await self._get_client()

            # Map action to zoom value (-100 to 100)
            # Positive = zoom in (tele), Negative = zoom out (wide)
            if action == "in":
                zoom_value = speed
            elif action == "out":
                zoom_value = -speed
            else:
                zoom_value = 0

            # PTZ continuous command
            xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
<PTZData version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
    <pan>0</pan>
    <tilt>0</tilt>
    <zoom>{zoom_value}</zoom>
</PTZData>"""

            response = await client.put(
                f"{self.base_url}/ISAPI/PTZCtrl/channels/1/continuous",
                content=xml_data,
                headers={"Content-Type": "application/xml"}
            )

            if response.status_code == 200:
                logger.info(f"PTZ zoom {action} (value={zoom_value}) executed")
                return True
            else:
                logger.warning(f"PTZ zoom failed: {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"PTZ zoom error: {e}")

        return False

    async def ptz_zoom_absolute(self, zoom_level: int) -> bool:
        """
        Set absolute zoom level.

        Args:
            zoom_level: 0-100 (0=wide, 100=tele)

        Returns:
            Success status
        """
        try:
            client = await self._get_client()

            xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
<PTZData>
    <AbsoluteHigh>
        <elevation>0</elevation>
        <azimuth>0</azimuth>
        <absoluteZoom>{zoom_level}</absoluteZoom>
    </AbsoluteHigh>
</PTZData>"""

            response = await client.put(
                f"{self.base_url}/ISAPI/PTZCtrl/channels/1/absolute",
                content=xml_data,
                headers={"Content-Type": "application/xml"}
            )

            if response.status_code == 200:
                logger.info(f"PTZ zoom set to {zoom_level}")
                return True

        except Exception as e:
            logger.error(f"PTZ absolute zoom error: {e}")

        return False

    async def get_ptz_status(self) -> Dict[str, Any]:
        """Get current PTZ position including zoom."""
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.base_url}/ISAPI/PTZCtrl/channels/1/status"
            )

            if response.status_code == 200:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(response.text)
                ns = {'hik': 'http://www.hikvision.com/ver20/XMLSchema'}

                return {
                    'zoom': int(root.findtext('.//hik:absoluteZoom', '0', ns) or 0),
                    'pan': int(root.findtext('.//hik:azimuth', '0', ns) or 0),
                    'tilt': int(root.findtext('.//hik:elevation', '0', ns) or 0)
                }

        except Exception as e:
            logger.error(f"PTZ status error: {e}")

        return {'zoom': 0, 'pan': 0, 'tilt': 0}
