from .queue import Track
from ..database import supabase

def create(user_id:int,name:str):
    name=name.strip()
    if not name or len(name)>80: raise ValueError("Nama playlist harus 1-80 karakter.")
    return supabase.table("playlists").insert({"user_id":user_id,"name":name}).execute()

def get(user_id:int,name:str):
    rows=supabase.table("playlists").select("*").eq("user_id",user_id).eq("name",name.strip()).limit(1).execute().data or []
    return rows[0] if rows else None

def list_all(user_id:int):
    return supabase.table("playlists").select("*").eq("user_id",user_id).order("name").execute().data or []

def delete(user_id:int,name:str):
    p=get(user_id,name)
    if not p: return False
    supabase.table("playlists").delete().eq("id",p["id"]).execute()
    return True

def rename(user_id:int,old:str,new:str):
    new=new.strip()
    if not new or len(new)>80: raise ValueError("Nama playlist harus 1-80 karakter.")
    p=get(user_id,old)
    if not p: return False
    supabase.table("playlists").update({"name":new}).eq("id",p["id"]).execute()
    return True

def add_track(user_id:int,name:str,track:Track,max_size:int=100):
    p=get(user_id,name)
    if not p: return False
    rows=supabase.table("playlist_tracks").select("position").eq("playlist_id",p["id"]).order("position",desc=True).limit(1).execute().data or []
    if rows and rows[0]["position"]>=max_size: raise ValueError("Playlist sudah penuh.")
    pos=(rows[0]["position"]+1) if rows else 1
    supabase.table("playlist_tracks").insert({"playlist_id":p["id"],"position":pos,"title":track.title,"source_url":track.webpage_url}).execute()
    return True

def remove_track(user_id:int,name:str,position:int):
    p=get(user_id,name)
    if not p: return False
    r=supabase.table("playlist_tracks").delete().eq("playlist_id",p["id"]).eq("position",position).execute()
    if not r.data: return False
    rows=supabase.table("playlist_tracks").select("position,title,source_url").eq("playlist_id",p["id"]).order("position").execute().data or []
    for index,row in enumerate(rows,1):
        if row["position"]!=index:
            supabase.table("playlist_tracks").update({"position":index}).eq("playlist_id",p["id"]).eq("position",row["position"]).execute()
    return True

def tracks(user_id:int,name:str):
    p=get(user_id,name)
    if not p: return []
    return supabase.table("playlist_tracks").select("*").eq("playlist_id",p["id"]).order("position").execute().data or []
