from bot.music.queue import GuildQueue,Track

def track(n):
    return Track(title=str(n),webpage_url=f"https://example.com/{n}")

def test_queue_loop_modes():
    q=GuildQueue()
    q.add(track("a")); q.add(track("b"))
    first=q.pop_next()
    assert first.title=="a"
    q.current=first
    q.loop="track"
    assert q.pop_next() is first
    q.loop="queue"
    q.current=first
    q.tracks.clear()
    q.add(track("b"))
    assert q.pop_next().title=="b"
    assert q.tracks[-1] is first

def test_move_and_remove():
    q=GuildQueue()
    for n in range(3): q.add(track(n))
    q.move(0,2)
    assert [t.title for t in q.tracks]==["1","2","0"]
    assert q.remove(1).title=="2"
    assert [t.title for t in q.tracks]==["1","0"]

def test_volume_bounds():
    q=GuildQueue()
    q.volume=1.5
    assert q.volume==1.5
