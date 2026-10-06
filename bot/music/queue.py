from dataclasses import dataclass, field
from typing import Optional
import time
import random

@dataclass
class Track:
    title: str
    webpage_url: str
    stream_url: Optional[str] = None
    duration: Optional[float] = None
    thumbnail: Optional[str] = None
    uploader: Optional[str] = None
    requested_by: Optional[int] = None

@dataclass
class GuildQueue:
    tracks: list[Track] = field(default_factory=list)
    current: Optional[Track] = None
    played: list[Track] = field(default_factory=list)
    loop: str = "off"
    volume: float = 1.0
    autoplay: bool = False
    always_connected: bool = False
    paused: bool = False
    position: float = 0.0
    filter: str = "off"
    speed: float = 1.0
    replay_current: bool = False
    started_at: float = 0.0
    started_offset: float = 0.0
    paused_at: float = 0.0
    effects_dirty: bool = False

    def add(self,track):
        self.tracks.append(track)

    def pop_next(self):
        if self.loop=="track" and self.current:
            return self.current
        if self.loop=="queue" and self.current:
            self.tracks.append(self.current)
        return self.tracks.pop(0) if self.tracks else None

    def clear(self):
        self.tracks.clear()

    def shuffle(self):
        random.shuffle(self.tracks)

    def remove(self,index):
        return self.tracks.pop(index)

    def move(self,source,target):
        item=self.tracks.pop(source)
        self.tracks.insert(target,item)
        return item
