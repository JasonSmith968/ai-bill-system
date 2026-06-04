"""Agent Memory Service — persistent user financial profiles and habit learning."""

import logging
from datetime import datetime
from extensions import db
from models.agent_memory import AgentMemory

logger = logging.getLogger(__name__)


class AgentMemoryService:
    """Service for managing agent memories (user profiles, habits, preferences)."""

    def recall(self, user_id, query_key, memory_type=None):
        """Retrieve a memory value by key. Returns None if not found or expired."""
        q = AgentMemory.query.filter_by(user_id=user_id, key=query_key)
        if memory_type:
            q = q.filter_by(memory_type=memory_type)
        mem = q.first()
        if not mem:
            return None
        if mem.expires_at and mem.expires_at < datetime.utcnow():
            return None
        return mem.value

    def remember(self, user_id, key, value, memory_type='fact', source='inferred', confidence=0.8):
        """Store or update a memory."""
        existing = AgentMemory.get_by_key(user_id, key)
        if existing:
            existing.value = value
            existing.memory_type = memory_type
            existing.source = source
            existing.update_confidence(True)
            if confidence > existing.confidence:
                existing.confidence = confidence
        else:
            mem = AgentMemory(
                user_id=user_id,
                memory_type=memory_type,
                key=key,
                value=value,
                confidence=confidence,
                source=source,
            )
            db.session.add(mem)
        db.session.commit()

    def get_profile(self, user_id):
        """Aggregate all preference/profile memories into a single dict."""
        memories = AgentMemory.get_user_memories(user_id, 'profile')
        prefs = AgentMemory.get_user_memories(user_id, 'prefer')
        profile = {}
        for mem in memories + prefs:
            if mem.confidence >= 0.5:
                profile[mem.key] = mem.value
        return profile

    def get_habits(self, user_id):
        """Aggregate all habit memories."""
        memories = AgentMemory.get_user_memories(user_id, 'habit')
        return [
            {'key': m.key, 'value': m.value, 'confidence': m.confidence}
            for m in memories if m.confidence >= 0.4
        ]

    def forget(self, user_id, key):
        """Delete a specific memory."""
        mem = AgentMemory.get_by_key(user_id, key)
        if mem:
            db.session.delete(mem)
            db.session.commit()
            return True
        return False

    def consolidate(self, user_id):
        """Remove low-confidence and expired memories."""
        now = datetime.utcnow()
        memories = AgentMemory.query.filter_by(user_id=user_id).all()
        removed = 0
        for mem in memories:
            if mem.confidence < 0.2 or (mem.expires_at and mem.expires_at < now):
                db.session.delete(mem)
                removed += 1
        if removed:
            db.session.commit()
        return removed

    def get_all(self, user_id, memory_type=None):
        """Get all memories for a user as a list of dicts."""
        memories = AgentMemory.get_user_memories(user_id, memory_type)
        return [m.to_dict() for m in memories]

    def infer_from_transactions(self, user_id, transactions):
        """Learn habits from transaction patterns. Called by analysis agents."""
        if not transactions:
            return

        # Learn spending categories
        from collections import Counter
        cat_counter = Counter()
        for t in transactions:
            cat_name = t.category.name if t.category else '未分类'
            cat_counter[cat_name] += 1

        if cat_counter:
            top_cats = [c for c, _ in cat_counter.most_common(3)]
            self.remember(user_id, 'top_categories', top_cats, 'habit', 'inferred', 0.7)

        # Learn average monthly spend
        amounts = [float(t.amount) for t in transactions if t.type == 'expense']
        if amounts:
            avg = sum(amounts) / max(len(amounts), 1)
            self.remember(user_id, 'avg_transaction_amount', round(avg, 2), 'habit', 'inferred', 0.6)
