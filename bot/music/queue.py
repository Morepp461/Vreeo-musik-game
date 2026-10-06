from dataclasses import dataclass, field
from typing import Optional
import random

@dataclass
class Track:
    title: str
    webpage_url: str
    stream_url: str
    duration: Optional[float] = None
    thumbnail: Optional[str] = None
    uploader: Optional[str] = None
    requested_by: Optional[int] = None

@dataclass
class GuildQueue:
    tracks: list[Track] = field(default_factory=list)
    current: Optional[Track] = None
    loop: str = "off"
    volume: float = 1.0
    autoplay: bool = False
    paused: bool = False

    def add(self, track: Track):
        self.tracks.append(track)

    def pop_next(self) -> Optional[Track]:
        if self.loop == "track" and self.current:
            return self.current
        if self.tracks:
            return self.tracks.pop(0)
        return None

    def clear(self):
        self.tracks.clear()

    def shuffle(self):
        random.shuffle(self.tracks)

    def remove(self, index: int) -> Track:
        return self.tracks.pop(index)
