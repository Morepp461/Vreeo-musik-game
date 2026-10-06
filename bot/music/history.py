from ..database import supabase

def record(user_id:int,title:str,url:str|None):
    return supabase.table("music_history").insert({"user_id":user_id,"title":title,"source_url":url}).execute()

def list_recent(user_id:int,limit:int=20):
    return supabase.table("music_history").select("*").eq("user_id",user_id).order("played_at",desc=True).limit(limit).execute().data or []

def clear(user_id:int):
    return supabase.table("music_history").delete().eq("user_id",user_id).execute()
