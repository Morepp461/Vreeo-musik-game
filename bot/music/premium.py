from collections import Counter
from datetime import datetime, timedelta, timezone
from ..database import supabase

MOODS = {
    "chill": ("Chill", ("chill music", "lofi chill", "smooth r&b", "relaxing music")),
    "focus": ("Focus", ("focus music", "deep focus", "study lofi", "instrumental focus")),
    "energy": ("Energy", ("EDM hits", "dance music", "workout music", "upbeat pop")),
    "happy": ("Happy", ("happy pop songs", "feel good music", "upbeat songs", "summer hits")),
    "sad": ("Sad", ("sad songs", "emotional songs", "melancholy music", "sad pop")),
    "romantic": ("Romantic", ("romantic songs", "love songs", "romantic r&b", "slow love songs")),
    "night": ("Night", ("late night music", "night drive music", "dark pop", "night r&b")),
}

def weekly(user_id:int):
    since=(datetime.now(timezone.utc)-timedelta(days=7)).isoformat()
    try:
        rows=supabase.table("music_history").select("title,source_url,played_at").eq("user_id",user_id).gte("played_at",since).order("played_at",desc=True).limit(500).execute().data or []
    except Exception:
        rows=[]
    counts=Counter((r.get("title") or "Unknown") for r in rows)
    artists=Counter()
    for title in counts:
        if " — " in title:
            artists[title.rsplit(" — ",1)[-1].strip() or "Unknown"] += counts[title]
    return {"rows":rows,"plays":len(rows),"songs":counts,"artists":artists}

def taste(user_id:int):
    data=weekly(user_id)
    try:
        fav=supabase.table("favorites").select("title").eq("user_id",user_id).limit(50).execute().data or []
    except Exception:
        fav=[]
    all_titles=[r.get("title") or "Unknown" for r in fav]
    all_titles += list(data["songs"].elements())
    genres=Counter()
    keywords={
        "Pop":("pop",),"Hip-Hop / Rap":("rap","hip hop","hip-hop"),"R&B":("r&b","rnb","soul"),
        "EDM":("edm","electronic","dance"),"Rock":("rock",),"Lo-fi / Chill":("lofi","chill"),
        "K-Pop":("k-pop","kpop"),"J-Pop":("j-pop","jpop"),"Indonesia":("indonesia","lagu "),
    }
    for title in all_titles:
        low=title.lower()
        for genre,words in keywords.items():
            if any(w in low for w in words): genres[genre]+=1
    return {"plays":data["plays"],"top_songs":data["songs"].most_common(5),"top_artists":data["artists"].most_common(5),"genres":genres.most_common(5)}

def discovery_queries(user_id:int):
    data=taste(user_id)
    queries=[]
    for artist,_ in data["top_artists"][:3]:
        if artist != "Unknown": queries.append(f"{artist} similar artists songs")
    for genre,_ in data["genres"][:2]:
        queries.append(f"best {genre.lower()} songs")
    if not queries:
        queries=["popular songs","new music","indie music"]
    return queries[:4]
