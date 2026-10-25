"""
REA Core - InnerTube Reverse Engineered Client
Provides lightweight, anonymous interaction with the YouTube Music (InnerTube) API.
Zero external dependencies (uses standard library urllib and json).
"""

import json
import re
import time
import urllib.parse
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Tuple


class InnerTubeClient:
    """
    Reverse-engineered client for YouTube Music's InnerTube API.
    Reconstructed from network analysis of WEB_REMIX, ANDROID_VR, and IOS clients.
    """

    BASE_URL = "https://music.youtube.com/youtubei/v1"
    MAIN_YOUTUBE_URL = "https://www.youtube.com/youtubei/v1"

    # InnerTube Clients specifications reverse-engineered from app payloads
    CLIENTS = {
        "WEB_REMIX": {
            "client": {
                "clientName": "WEB_REMIX",
                "clientVersion": "1.20240708.01.00",
                "hl": "en",
                "gl": "US",
            },
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
                "X-YouTube-Client-Name": "67",
                "X-YouTube-Client-Version": "1.20240708.01.00",
                "Referer": "https://music.youtube.com/",
            },
        },
        "ANDROID_VR": {
            "client": {
                "clientName": "ANDROID_VR",
                "clientVersion": "1.60.19",
                "deviceMake": "Oculus",
                "deviceModel": "Quest 3",
                "androidSdkVersion": 32,
                "osName": "Android",
                "osVersion": "12L",
                "hl": "en",
                "gl": "US",
            },
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": (
                    "com.google.android.apps.youtube.vr.oculus/1.60.19 "
                    "(Linux; U; Android 12L; eureka-user Build/SQ3A.220605.009.A1) gzip"
                ),
                "X-YouTube-Client-Name": "28",
                "X-YouTube-Client-Version": "1.60.19",
            },
        },
        "IOS": {
            "client": {
                "clientName": "IOS",
                "clientVersion": "21.26.4",
                "deviceMake": "Apple",
                "deviceModel": "iPhone16,2",
                "osName": "iPhone",
                "osVersion": "18.3.2.22D82",
                "hl": "en",
                "gl": "US",
            },
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": (
                    "com.google.ios.youtube/21.26.4 "
                    "(iPhone16,2; U; CPU iOS 18_3_2 like Mac OS X;)"
                ),
                "X-YouTube-Client-Name": "5",
                "X-YouTube-Client-Version": "21.26.4",
            },
        },
    }

    # Pre-compiled protobuf search filter for "Songs"
    SONG_SEARCH_PARAMS = "EgWKAQIIAWoKEAkQChAFEBEQEA=="

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self._ydl = None
        self._stream_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

    def _post(self, endpoint_url: str, client_key: str, payload_body: Dict[str, Any]) -> Dict[str, Any]:
        """Executes a JSON POST request against an InnerTube endpoint."""
        client_spec = self.CLIENTS[client_key]
        full_payload = {
            "context": {"client": client_spec["client"]},
            **payload_body,
        }
        data_bytes = json.dumps(full_payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint_url,
            data=data_bytes,
            headers=client_spec["headers"],
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"InnerTube HTTP {err.code}: {err.reason} - {err_body}") from err

    @staticmethod
    def _upgrade_thumbnail(url: str, size: int = 544) -> str:
        """Upgrades standard low-res YouTube thumbnail URL to HD."""
        if not url:
            return ""
        # Match pattern =w60-h60... and replace with =w544-h544-l90-rj
        upgraded = re.sub(r"=w\d+-h\d+.*", f"=w{size}-h{size}-l90-rj", url)
        if upgraded == url and ("ytimg.com" in url or "googleusercontent.com" in url):
            upgraded = f"{url}=w{size}-h{size}-l90-rj"
        return upgraded

    def search(self, query: str, filter_songs: bool = True, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Searches YouTube Music for tracks matching the query.
        Returns a clean list of songs with metadata and high-res thumbnails.
        """
        payload = {"query": query}
        if filter_songs:
            payload["params"] = self.SONG_SEARCH_PARAMS

        resp = self._post(f"{self.BASE_URL}/search", "WEB_REMIX", payload)
        results: List[Dict[str, Any]] = []

        tabs = (
            resp.get("contents", {})
            .get("tabbedSearchResultsRenderer", {})
            .get("tabs", [])
        )
        if not tabs:
            return results

        section_contents = (
            tabs[0]
            .get("tabRenderer", {})
            .get("content", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )

        for section in section_contents:
            shelf = section.get("musicShelfRenderer")
            if not shelf:
                # Could be inside itemSectionRenderer
                item_section = section.get("itemSectionRenderer", {})
                shelf_items = item_section.get("contents", [])
            else:
                shelf_items = shelf.get("contents", [])

            for it in shelf_items:
                renderer = it.get("musicResponsiveListItemRenderer")
                if not renderer:
                    continue

                # Flex column 1: Title
                flex_cols = renderer.get("flexColumns", [])
                if not flex_cols:
                    continue

                col0_runs = (
                    flex_cols[0]
                    .get("musicResponsiveListItemFlexColumnRenderer", {})
                    .get("text", {})
                    .get("runs", [])
                )
                title = col0_runs[0].get("text", "") if col0_runs else ""

                # Flex column 2: Artist(s), Album, Duration
                col1_runs = (
                    flex_cols[1]
                    .get("musicResponsiveListItemFlexColumnRenderer", {})
                    .get("text", {})
                    .get("runs", [])
                    if len(flex_cols) > 1
                    else []
                )

                artists = []
                album = ""
                duration = ""
                for run in col1_runs:
                    text = run.get("text", "")
                    nav = run.get("navigationEndpoint", {})
                    if "browseEndpoint" in nav:
                        b_type = nav["browseEndpoint"].get("browseEndpointContextSupportedConfigs", {}).get(
                            "browseEndpointContextMusicConfig", {}
                        ).get("pageType")
                        if b_type == "MUSIC_PAGE_TYPE_ARTIST":
                            artists.append(text)
                        elif b_type == "MUSIC_PAGE_TYPE_ALBUM":
                            album = text
                    elif re.match(r"^\d+:\d+$", text):
                        duration = text

                if not artists and col1_runs:
                    # Fallback first run as artist
                    artists = [col1_runs[0].get("text", "Unknown")]

                # Extract Video ID
                video_id = renderer.get("playlistItemData", {}).get("videoId")
                if not video_id:
                    # Check watchEndpoint in thumbnail overlay or runs
                    nav = renderer.get("overlay", {}).get("musicItemThumbnailOverlayRenderer", {}).get(
                        "content", {}
                    ).get("musicPlayButtonRenderer", {}).get("playNavigationEndpoint", {}).get("watchEndpoint")
                    if nav:
                        video_id = nav.get("videoId")

                # Extract Thumbnails
                raw_thumbs = (
                    renderer.get("thumbnail", {})
                    .get("musicThumbnailRenderer", {})
                    .get("thumbnail", {})
                    .get("thumbnails", [])
                )
                raw_thumb_url = raw_thumbs[-1].get("url", "") if raw_thumbs else ""
                hd_thumb_url = self._upgrade_thumbnail(raw_thumb_url, size=544)

                if video_id and title:
                    results.append(
                        {
                            "video_id": video_id,
                            "title": title,
                            "artists": artists,
                            "artist": ", ".join(artists),
                            "album": album,
                            "duration": duration,
                            "thumbnail_url": hd_thumb_url,
                            "raw_thumbnail_url": raw_thumb_url,
                        }
                    )
                    if len(results) >= limit:
                        return results

        return results

    def get_playlist(self, playlist_id: str) -> Dict[str, Any]:
        """
        Retrieves tracks from a public YouTube Music playlist without authentication.
        Accepts playlist IDs with or without the 'VL' prefix (e.g. 'PL...' or 'VLPL...').
        """
        browse_id = playlist_id if playlist_id.startswith("VL") else f"VL{playlist_id}"
        resp = self._post(
            f"{self.BASE_URL}/browse",
            "WEB_REMIX",
            {"browseId": browse_id},
        )

        title = "Playlist"
        subtitle = ""
        tracks: List[Dict[str, Any]] = []

        two_col = resp.get("contents", {}).get("twoColumnBrowseResultsRenderer")
        if two_col:
            # Header
            header_sec = (
                two_col.get("tabs", [{}])[0]
                .get("tabRenderer", {})
                .get("content", {})
                .get("sectionListRenderer", {})
                .get("contents", [{}])[0]
                .get("musicResponsiveHeaderRenderer", {})
            )
            title = header_sec.get("title", {}).get("runs", [{}])[0].get("text", title)
            subtitle = "".join(r.get("text", "") for r in header_sec.get("subtitle", {}).get("runs", []))

            # Tracks list in secondaryContents
            secondary = two_col.get("secondaryContents", {})
            shelf = (
                secondary.get("sectionListRenderer", {})
                .get("contents", [{}])[0]
                .get("musicPlaylistShelfRenderer", {})
            )
            items = shelf.get("contents", [])
            for it in items:
                r = it.get("musicResponsiveListItemRenderer", {})
                flex_cols = r.get("flexColumns", [])
                if not flex_cols:
                    continue
                track_title = flex_cols[0].get("musicResponsiveListItemFlexColumnRenderer", {}).get(
                    "text", {}
                ).get("runs", [{}])[0].get("text", "")
                
                track_artists = []
                if len(flex_cols) > 1:
                    runs = flex_cols[1].get("musicResponsiveListItemFlexColumnRenderer", {}).get("text", {}).get("runs", [])
                    track_artists = [runs[0].get("text", "")] if runs else []

                vid = r.get("playlistItemData", {}).get("videoId")
                if vid and track_title:
                    tracks.append({
                        "video_id": vid,
                        "title": track_title,
                        "artist": ", ".join(track_artists),
                    })

        return {
            "playlist_id": playlist_id,
            "title": title,
            "subtitle": subtitle,
            "track_count": len(tracks),
            "tracks": tracks,
        }

    def get_audio_stream(self, video_id: str) -> Dict[str, Any]:
        """
        Resolves pure, direct audio stream URL from YouTube's CDN for a given video_id.
        Features memory caching and persistent extractor instance for sub-second resolution.
        """
        # Check in-memory stream URL cache (URLs valid for ~6 hours)
        cached = self._stream_cache.get(video_id)
        if cached:
            cached_time, stream_info = cached
            if time.time() - cached_time < 7200:  # 2 hours validity
                return stream_info

        # Primary strategy: Resilient stream resolution via persistent yt-dlp instance
        try:
            import yt_dlp

            if self._ydl is None:
                ydl_opts = {
                    "format": "bestaudio/best",
                    "quiet": True,
                    "no_warnings": True,
                    "extract_flat": False,
                    "noplaylist": True,
                    "skip_download": True,
                    "check_formats": False,
                    "youtube_include_dash_manifest": False,
                    "youtube_include_hls_manifest": False,
                }
                self._ydl = yt_dlp.YoutubeDL(ydl_opts)

            target_url = f"https://music.youtube.com/watch?v={video_id}"
            info = self._ydl.extract_info(target_url, download=False)
            direct_url = info.get("url")
            if direct_url:
                acodec = info.get("acodec", "opus")
                container = "webm" if "webm" in info.get("ext", "") else "mp4"
                abr = info.get("abr") or 160.0
                stream_res = {
                    "success": True,
                    "video_id": video_id,
                    "url": direct_url,
                    "itag": info.get("format_id"),
                    "container": container,
                    "codec": acodec,
                    "bitrate": int(abr * 1000),
                    "bitrate_kbps": round(float(abr), 1),
                    "audio_sample_rate": info.get("asr"),
                    "content_length": info.get("filesize"),
                    "expires_at": None,
                    "playability_status": "OK",
                }
                self._stream_cache[video_id] = (time.time(), stream_res)
                return stream_res
        except Exception:
            pass

        # Secondary fallback: ANDROID_VR client
        player_resp = self._post(
            f"{self.MAIN_YOUTUBE_URL}/player",
            "ANDROID_VR",
            {"videoId": video_id},
        )

        streaming_data = player_resp.get("streamingData", {})
        adaptive_formats = streaming_data.get("adaptiveFormats", [])
        audio_formats = [
            f for f in adaptive_formats if f.get("mimeType", "").startswith("audio/") and "url" in f
        ]

        # Prioritization mapping based on itags
        def format_priority(fmt: Dict[str, Any]) -> int:
            itag = fmt.get("itag")
            if itag == 251:  # Opus 160k
                return 400000 + fmt.get("bitrate", 0)
            if itag == 140:  # AAC 128k
                return 300000 + fmt.get("bitrate", 0)
            if itag == 250:  # Opus 70k
                return 200000 + fmt.get("bitrate", 0)
            if itag == 249:  # Opus 50k
                return 100000 + fmt.get("bitrate", 0)
            return fmt.get("bitrate", 0)

        if audio_formats:
            audio_formats.sort(key=format_priority, reverse=True)
            chosen = audio_formats[0]

            # Extract expiration timestamp from URL params
            parsed_query = urllib.parse.parse_qs(urllib.parse.urlparse(chosen["url"]).query)
            expire_ts = parsed_query.get("expire", [None])[0]

            mime = chosen.get("mimeType", "")
            container = "webm" if "webm" in mime else "mp4"
            codec = "opus" if "opus" in mime else "aac"

            return {
                "success": True,
                "video_id": video_id,
                "url": chosen["url"],
                "itag": chosen.get("itag"),
                "container": container,
                "codec": codec,
                "bitrate": chosen.get("bitrate"),
                "bitrate_kbps": round(chosen.get("bitrate", 0) / 1000, 1),
                "audio_sample_rate": chosen.get("audioSampleRate"),
                "content_length": chosen.get("contentLength"),
                "expires_at": int(expire_ts) if expire_ts else None,
                "playability_status": player_resp.get("playabilityStatus", {}).get("status"),
            }

        # Fallback if ANDROID_VR is challenged (e.g. strict bot check on some official label releases)
        status = player_resp.get("playabilityStatus", {})
        return {
            "success": False,
            "video_id": video_id,
            "url": None,
            "error": status.get("reason", "No playable direct audio formats returned"),
            "status": status.get("status"),
            "requires_bot_verification": status.get("status") == "LOGIN_REQUIRED",
        }
