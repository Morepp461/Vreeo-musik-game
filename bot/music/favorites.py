from .queue import Track
from ..database import supabase

def add(user_id:int, track:Track):
    return supabase.table("favorites").upsert({"user_id":user_id,"title":track.title,"source_url":track.webpage_url}).execute()

def remove(user_id:int, url:str):
    return supabase.table("favorites").delete().eq("user_id",user_id).eq("source_url",url).execute()

def list_all(user_id:int):
    return supabase.table("favorites").select("*").eq("user_id",user_id).order("created_at",desc=True).limit(50).execute().data or []
