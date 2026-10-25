"""
REA Core - Synchronized Lyrics Engine
Reconstructed lyrics parser supporting .lrc timestamped sync from LRCLIB
with automatic fallback to YouTube Music's InnerTube lyrics endpoint.
"""

import json
import re
import urllib.parse
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional


class LyricsEngine:
    """
    Fetches and parses timestamped (.lrc) synchronized lyrics
    as well as plain-text lyrics from open endpoints.
    """

    LRCLIB_BASE = "https://lrclib.net/api"
    INNERTUBE_NEXT = "https://music.youtube.com/youtubei/v1/next"
    INNERTUBE_BROWSE = "https://music.youtube.com/youtubei/v1/browse"

    INNERTUBE_HEADERS = {
        "Content-Type": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "X-YouTube-Client-Name": "67",
        "X-YouTube-Client-Version": "1.20240708.01.00",
        "Referer": "https://music.youtube.com/",
    }

    def __init__(self, timeout: int = 6):
        self.timeout = timeout

    @staticmethod
    def clean_title(title: str) -> str:
        """Strips noise such as '(Official Music Video)' and '(feat. ...)' from song titles."""
        if not title:
            return ""
        # Remove parenthetical tags like (Official Video), [Audio], etc.
        patterns = [
            r"\(feat\..*?\)",
            r"\[feat\..*?\]",
            r"\(part\..*?\)",
            r"\[part\..*?\]",
            r"\(official.*?\)",
            r"\[official.*?\]",
            r"\(video.*?\)",
            r"\[video.*?\]",
            r"\(audio.*?\)",
            r"\[audio.*?\]",
            r"\(clipe.*?\)",
            r"\[clipe.*?\]",
            r"\(remastered.*?\)",
            r"\[remastered.*?\]",
        ]
        cleaned = title
        for pat in patterns:
            cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    @staticmethod
    def clean_artist(artist: str) -> str:
        """Extracts the primary artist name."""
        if not artist:
            return ""
        # Split on commas, feat., &, or e
        primary = re.split(r",|;| & | e | feat\.? ", artist, flags=re.IGNORECASE)[0]
        return primary.strip()

    @classmethod
    def parse_lrc(cls, lrc_text: str) -> List[Dict[str, Any]]:
        """
        Parses LRC content containing [mm:ss.xx] timestamps into an ordered list of line objects:
        [{ "time": float_seconds, "text": "line text" }]
        """
        lines: List[Dict[str, Any]] = []
        if not lrc_text:
            return lines

        # Extract standard LRC [offset:+/-ms] tag if present
        offset_sec = 0.0
        offset_pattern = re.compile(r"\[offset:\s*([+-]?\d+)\s*\]", re.IGNORECASE)
        for raw_line in lrc_text.splitlines()[:20]:
            off_m = offset_pattern.search(raw_line)
            if off_m:
                try:
                    # In LRC standard: positive offset means audio is ahead, so add to timestamp
                    offset_sec = float(off_m.group(1)) / 1000.0
                    break
                except ValueError:
                    pass

        time_pattern = re.compile(r"\[(\d{1,2}):(\d{2}(?:\.\d+)?)\]")

        for raw_line in lrc_text.splitlines():
            raw_line = raw_line.strip()
            if not raw_line:
                continue

            matches = list(time_pattern.finditer(raw_line))
            if not matches:
                continue

            # Extract lyrics text appearing after the final timestamp tag
            last_match = matches[-1]
            text = raw_line[last_match.end():].strip()

            for match in matches:
                mins = int(match.group(1))
                secs = float(match.group(2))
                t = max(0.0, round(mins * 60 + secs + offset_sec, 2))
                lines.append({"time": t, "text": text})

        lines.sort(key=lambda item: item["time"])
        return lines

    def _fetch_lrclib_record(self, track_name: str, artist_name: str, duration: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Queries the /api/get endpoint of LRCLIB."""
        params_dict = {
            "track_name": track_name,
            "artist_name": artist_name,
        }
        if duration and duration > 0:
            params_dict["duration"] = str(int(duration))

        query_str = urllib.parse.urlencode(params_dict)
        url = f"{self.LRCLIB_BASE}/get?{query_str}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            return None
        return None

    def fetch_lrclib(self, title: str, artist: str, duration_sec: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Attempts to resolve lyrics from LRCLIB using exact and cleaned names.
        Returns parsed line items and metadata.
        """
        dur_int = int(duration_sec) if duration_sec and duration_sec > 0 else None

        # Attempt 1: Exact names with duration
        res = self._fetch_lrclib_record(title, artist, dur_int)

        # Attempt 2: Cleaned names with duration
        if not res:
            c_title = self.clean_title(title)
            c_artist = self.clean_artist(artist)
            if c_title != title or c_artist != artist:
                res = self._fetch_lrclib_record(c_title, c_artist, dur_int)

        # Attempt 3: Cleaned names without duration restriction
        if not res:
            c_title = self.clean_title(title)
            c_artist = self.clean_artist(artist)
            res = self._fetch_lrclib_record(c_title, c_artist, None)

        if res:
            synced = res.get("syncedLyrics")
            if synced:
                parsed_lines = self.parse_lrc(synced)
                if parsed_lines:
                    return {
                        "is_synced": True,
                        "source": "LRCLIB (Synced)",
                        "lines": parsed_lines,
                    }

            plain = res.get("plainLyrics")
            if plain:
                plain_lines = [{"time": None, "text": line.strip()} for line in plain.splitlines() if line.strip()]
                return {
                    "is_synced": False,
                    "source": "LRCLIB (Plain Text)",
                    "lines": plain_lines,
                }

        return None

    def fetch_innertube_lyrics(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Fallback lyrics retrieval using YouTube Music's InnerTube browseId (MPLY...).
        """
        if not video_id:
            return None

        # Step 1: Query /next to get lyrics browseId
        next_payload = {
            "context": {
                "client": {
                    "clientName": "WEB_REMIX",
                    "clientVersion": "1.20240708.01.00",
                    "hl": "pt-BR",
                    "gl": "BR",
                }
            },
            "videoId": video_id,
        }

        try:
            req_next = urllib.request.Request(
                self.INNERTUBE_NEXT,
                data=json.dumps(next_payload).encode("utf-8"),
                headers=self.INNERTUBE_HEADERS,
                method="POST",
            )
            with urllib.request.urlopen(req_next, timeout=self.timeout) as resp:
                next_data = json.loads(resp.read().decode("utf-8"))

            tabs = (
                next_data.get("contents", {})
                .get("singleColumnMusicWatchNextResultsRenderer", {})
                .get("tabbedRenderer", {})
                .get("watchNextTabbedResultsRenderer", {})
                .get("tabs", [])
            )

            lyrics_browse_id = None
            for tab in tabs:
                tab_ren = tab.get("tabRenderer", {})
                title = tab_ren.get("title", "").lower()
                if "letra" in title or "lyrics" in title:
                    lyrics_browse_id = tab_ren.get("endpoint", {}).get("browseEndpoint", {}).get("browseId")
                    break

            if not lyrics_browse_id:
                return None

            # Step 2: Query /browse with lyrics browseId
            browse_payload = {
                "context": {
                    "client": {
                        "clientName": "WEB_REMIX",
                        "clientVersion": "1.20240708.01.00",
                        "hl": "pt-BR",
                        "gl": "BR",
                    }
                },
                "browseId": lyrics_browse_id,
            }
            req_browse = urllib.request.Request(
                self.INNERTUBE_BROWSE,
                data=json.dumps(browse_payload).encode("utf-8"),
                headers=self.INNERTUBE_HEADERS,
                method="POST",
            )
            with urllib.request.urlopen(req_browse, timeout=self.timeout) as resp:
                browse_data = json.loads(resp.read().decode("utf-8"))

            section = (
                browse_data.get("contents", {})
                .get("sectionListRenderer", {})
                .get("contents", [{}])[0]
            )
            shelf = section.get("musicDescriptionShelfRenderer", {})
            runs = shelf.get("description", {}).get("runs", [])
            if runs:
                text_content = runs[0].get("text", "")
                plain_lines = [
                    {"time": None, "text": line.strip()}
                    for line in text_content.splitlines()
                    if line.strip()
                ]
                return {
                    "is_synced": False,
                    "source": "YouTube Music (Plain Text)",
                    "lines": plain_lines,
                }
        except Exception:
            return None

        return None

    def get_lyrics(
        self,
        title: str,
        artist: str,
        video_id: Optional[str] = None,
        duration_sec: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Unified lyrics fetcher:
          1. Queries LRCLIB for timestamped .lrc synchronized lyrics.
          2. Falls back to plain text from LRCLIB if synced is absent.
          3. Falls back to YouTube Music's InnerTube browse endpoint.
        """
        # 1. Primary: LRCLIB (Synchronized LRC)
        lrclib_res = self.fetch_lrclib(title, artist, duration_sec)
        if lrclib_res and lrclib_res.get("is_synced"):
            return {
                "success": True,
                **lrclib_res,
            }

        # 2. Secondary: InnerTube Native Lyrics (if video_id available)
        if video_id:
            yt_res = self.fetch_innertube_lyrics(video_id)
            if yt_res:
                return {
                    "success": True,
                    **yt_res,
                }

        # 3. Tertiary: Plain text from LRCLIB if found
        if lrclib_res:
            return {
                "success": True,
                **lrclib_res,
            }

        return {
            "success": False,
            "is_synced": False,
            "source": "None",
            "lines": [],
        }
