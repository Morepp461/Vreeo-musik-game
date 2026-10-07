import discord
from ..database import supabase


def record_memory(character_id, subject_type, subject_id, memory_type, summary, emotional_weight=0, importance=50, metadata=None):
    result = supabase.rpc(
        "game_record_ai_memory",
        {
            "p_character_id": int(character_id),
            "p_subject_type": str(subject_type),
            "p_subject_id": str(subject_id),
            "p_memory_type": str(memory_type),
            "p_summary": str(summary),
            "p_emotional_weight": int(emotional_weight),
            "p_importance": int(importance),
            "p_metadata": metadata or {},
        },
    ).execute()
    data = result.data
    if isinstance(data, list):
        return data[0] if data else None
    return data


def adjust_reputation(observer_character_id, subject_type, subject_id, reputation_delta=0, trust_delta=0, respect_delta=0, familiarity_delta=1, metadata=None):
    result = supabase.rpc(
        "game_adjust_ai_reputation",
        {
            "p_observer_character_id": int(observer_character_id),
            "p_subject_type": str(subject_type),
            "p_subject_id": str(subject_id),
            "p_reputation_delta": int(reputation_delta),
            "p_trust_delta": int(trust_delta),
            "p_respect_delta": int(respect_delta),
            "p_familiarity_delta": int(familiarity_delta),
            "p_metadata": metadata or {},
        },
    ).execute()
    data = result.data
    if isinstance(data, list):
        return data[0] if data else None
    return data


def sync_relationship_reputations(limit=250):
    rows = (
        supabase.table("game_relationships")
        .select("character_a,character_b,relation_type,affinity,status,metadata")
        .eq("status", "active")
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )
    synced = 0
    for row in rows:
        affinity = int(row.get("affinity") or 0)
        subject = str(row["character_b"])
        relation = str(row.get("relation_type") or "teman")
        adjust_reputation(
            row["character_a"],
            "ai",
            subject,
            reputation_delta=max(-5, min(5, affinity // 20)),
            trust_delta=max(-4, min(4, affinity // 25)),
            respect_delta=max(-3, min(3, affinity // 30)),
            familiarity_delta=1,
            metadata={"source": "relationship_sync", "relation_type": relation},
        )
        synced += 1
    return synced


def remember_recent_ai_events(limit=250):
    rows = (
        supabase.table("game_ai_life_events")
        .select("id,character_id,event_type,description,city,metadata,occurred_at")
        .order("occurred_at", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )
    recorded = 0
    for row in rows:
        record_memory(
            row["character_id"],
            "world_event",
            str(row["id"]),
            str(row.get("event_type") or "life_event"),
            str(row.get("description") or "Peristiwa kehidupan terjadi."),
            emotional_weight=int((row.get("metadata") or {}).get("emotional_weight", 0)),
            importance=int((row.get("metadata") or {}).get("importance", 50)),
            metadata={
                "source": "ai_life_event",
                "city": row.get("city"),
                "occurred_at": row.get("occurred_at"),
            },
        )
        recorded += 1
    return recorded


def sync_batch_7(limit=250):
    memories = remember_recent_ai_events(limit)
    reputations = sync_relationship_reputations(limit)
    return {"memories": memories, "reputations": reputations}


def memory_embed(limit=8):
    rows = (
        supabase.table("game_ai_memories")
        .select("character_id,memory_type,summary,emotional_weight,importance,occurred_at")
        .order("occurred_at", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )
    e = discord.Embed(
        title="🧠 Memori NPC",
        description="Peristiwa yang disimpan NPC sebagai pengalaman dunia.",
        color=discord.Color.purple(),
    )
    if not rows:
        e.description = "Belum ada memori NPC yang tersimpan."
    names = {}
    for row in rows:
        cid = row["character_id"]
        if cid not in names:
            found = supabase.table("game_ai_characters").select("name").eq("id", cid).limit(1).execute().data
            names[cid] = found[0]["name"] if found else "Unknown"
        mood = int(row.get("emotional_weight") or 0)
        marker = "🟢" if mood > 0 else "🔴" if mood < 0 else "⚪"
        e.add_field(
            name=f"{marker} {names[cid]} • {row.get('memory_type') or 'memory'}",
            value=f"{row.get('summary') or '—'}\nImportance: {row.get('importance', 0)}/100",
            inline=False,
        )
    return e


def reputation_embed(limit=8):
    rows = (
        supabase.table("game_ai_reputations")
        .select("observer_character_id,subject_type,subject_id,reputation_score,trust_score,respect_score,familiarity,interactions_count")
        .order("reputation_score", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )
    e = discord.Embed(
        title="⭐ Reputasi NPC",
        description="Cara NPC menilai pihak lain berdasarkan pengalaman dan hubungan.",
        color=discord.Color.gold(),
    )
    if not rows:
        e.description = "Belum ada reputasi yang terbentuk."
    names = {}
    for row in rows:
        observer = row["observer_character_id"]
        subject = row["subject_id"]
        if observer not in names:
            found = supabase.table("game_ai_characters").select("name").eq("id", observer).limit(1).execute().data
            names[observer] = found[0]["name"] if found else "Unknown"
        if row["subject_type"] == "ai":
            found = supabase.table("game_ai_characters").select("name").eq("id", int(subject)).limit(1).execute().data
            subject_name = found[0]["name"] if found else f"AI #{subject}"
        else:
            subject_name = f"{row['subject_type']}:{subject}"
        e.add_field(
            name=f"{names[observer]} → {subject_name}",
            value=(
                f"Reputasi **{row['reputation_score']}** • "
                f"Trust **{row['trust_score']}** • Respect **{row['respect_score']}**\n"
                f"Familiarity {row['familiarity']}/100 • Interaksi {row['interactions_count']}"
            ),
            inline=False,
        )
    return e
