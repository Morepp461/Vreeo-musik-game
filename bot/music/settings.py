from ..database import supabase

KEY="music_channel_id"

def set_channel(channel_id:int|None):
    value={"channel_id":channel_id}
    return supabase.table("bot_settings").upsert({"key":KEY,"value":value}).execute()

def get_channel():
    rows=supabase.table("bot_settings").select("value").eq("key",KEY).limit(1).execute().data or []
    return (rows[0].get("value") or {}).get("channel_id") if rows else None
