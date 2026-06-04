"""Prompt Registry — centralized prompt management with versioning and A/B testing.

Provides:
- Versioned prompt storage (DB-backed with in-memory defaults)
- A/B testing by weighted random selection
- Rollback to any previous version
- Per-agent prompt override support
"""

import random
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_registry = None


def get_prompt_registry() -> 'PromptRegistry':
    """Get or create the singleton PromptRegistry."""
    global _registry
    if _registry is None:
        _registry = PromptRegistry()
    return _registry


class PromptRegistry:
    """Centralized prompt registry with versioning and A/B testing.

    Prompts are stored in the PromptTemplate table with version numbers.
    A/B variants are stored as multiple active versions with weights.
    """

    def register(self, name: str, template: str, agent_name: Optional[str] = None,
                 variables: Optional[list] = None, weight: float = 1.0) -> int:
        """Register a new prompt version.

        Args:
            name: Prompt name (e.g. 'system_finance', 'spending_analysis')
            template: The prompt template text
            agent_name: Associated agent (optional)
            variables: List of variable names in the template
            weight: A/B testing weight (1.0 = sole active version)

        Returns:
            The new version number
        """
        try:
            from models.prompt_template import PromptTemplate
            from extensions import db

            # Get current max version
            latest = (
                PromptTemplate.query
                .filter_by(name=name)
                .order_by(PromptTemplate.version.desc())
                .first()
            )
            next_version = (latest.version + 1) if latest else 1

            # Deactivate previous versions if this is not an A/B variant
            if weight >= 1.0:
                PromptTemplate.query.filter_by(
                    name=name, is_active=True
                ).update({'is_active': False})

            tmpl = PromptTemplate(
                name=name,
                agent_name=agent_name,
                template=template,
                variables=variables or [],
                version=next_version,
                is_active=True,
                ab_weight=weight if weight < 1.0 else 0.0,
            )
            db.session.add(tmpl)
            db.session.commit()

            logger.info(f"Registered prompt '{name}' v{next_version} (weight={weight})")
            return next_version

        except Exception as e:
            logger.error(f"Failed to register prompt '{name}': {e}")
            try:
                from extensions import db
                db.session.rollback()
            except Exception:
                pass
            return 0

    def get_prompt(self, name: str, agent_name: Optional[str] = None) -> Optional[str]:
        """Get the active prompt template.

        For A/B variants, selects based on weight. Falls back to built-in defaults.

        Args:
            name: Prompt name
            agent_name: Agent name (for agent-specific prompts)

        Returns:
            Template string or None
        """
        # Try DB
        try:
            from models.prompt_template import PromptTemplate

            candidates = (
                PromptTemplate.query
                .filter_by(name=name, is_active=True)
                .all()
            )

            if candidates:
                # A/B selection by weight
                if len(candidates) > 1:
                    return self._weighted_select(candidates)
                return candidates[0].template

            # Try agent-specific prompt
            if agent_name:
                tmpl = PromptTemplate.get_active(f'system_{agent_name}', agent_name)
                if tmpl:
                    return tmpl.template

        except Exception as e:
            logger.debug(f"DB prompt lookup failed for '{name}': {e}")

        # Fallback to built-in defaults
        from agents.prompt_manager import DEFAULT_SYSTEM_PROMPTS, DEFAULT_TEMPLATES

        if name.startswith('system_'):
            agent = name[7:]  # strip 'system_'
            return DEFAULT_SYSTEM_PROMPTS.get(agent)

        return DEFAULT_TEMPLATES.get(name)

    def get_system_prompt(self, agent_name: str) -> str:
        """Get system prompt for an agent (convenience method)."""
        prompt = self.get_prompt(f'system_{agent_name}', agent_name)
        if prompt:
            return prompt

        # Final fallback
        from agents.prompt_manager import DEFAULT_SYSTEM_PROMPTS
        return DEFAULT_SYSTEM_PROMPTS.get(agent_name, DEFAULT_SYSTEM_PROMPTS.get('finance'))

    def rollback(self, name: str, version: int) -> bool:
        """Rollback a prompt to a specific version.

        Args:
            name: Prompt name
            version: Target version number

        Returns:
            True if rollback succeeded
        """
        try:
            from models.prompt_template import PromptTemplate
            from extensions import db

            # Find the target version
            target = PromptTemplate.query.filter_by(
                name=name, version=version
            ).first()

            if not target:
                logger.warning(f"Prompt '{name}' v{version} not found")
                return False

            # Deactivate all current versions
            PromptTemplate.query.filter_by(
                name=name, is_active=True
            ).update({'is_active': False})

            # Activate the target version
            target.is_active = True
            db.session.commit()

            logger.info(f"Rolled back prompt '{name}' to v{version}")
            return True

        except Exception as e:
            logger.error(f"Rollback failed for '{name}' v{version}: {e}")
            try:
                from extensions import db
                db.session.rollback()
            except Exception:
                pass
            return False

    def list_versions(self, name: str) -> list[dict]:
        """List all versions of a prompt.

        Returns:
            List of {version, is_active, ab_weight, created_at}
        """
        try:
            from models.prompt_template import PromptTemplate

            versions = (
                PromptTemplate.query
                .filter_by(name=name)
                .order_by(PromptTemplate.version.desc())
                .all()
            )

            return [
                {
                    'version': v.version,
                    'is_active': v.is_active,
                    'ab_weight': getattr(v, 'ab_weight', 0.0),
                    'template_preview': v.template[:100] + '...' if len(v.template) > 100 else v.template,
                }
                for v in versions
            ]

        except Exception as e:
            logger.error(f"Failed to list versions for '{name}': {e}")
            return []

    def get_ab_stats(self, name: str) -> dict:
        """Get A/B testing statistics for a prompt.

        Returns:
            {variants: [{version, weight, usage_count, success_rate}]}
        """
        try:
            from models.prompt_template import PromptTemplate
            from models.agent_log import AgentExecutionLog

            variants = (
                PromptTemplate.query
                .filter_by(name=name, is_active=True)
                .all()
            )

            result = []
            for v in variants:
                # Count usage from agent logs (approximate)
                usage_count = (
                    AgentExecutionLog.query
                    .filter_by(agent_name=v.agent_name or '')
                    .filter(AgentExecutionLog.created_at >= v.created_at if hasattr(v, 'created_at') else True)
                    .count()
                ) if v.agent_name else 0

                result.append({
                    'version': v.version,
                    'weight': getattr(v, 'ab_weight', 0.0),
                    'usage_count': usage_count,
                })

            return {'variants': result}

        except Exception as e:
            logger.error(f"Failed to get A/B stats for '{name}': {e}")
            return {'variants': []}

    def _weighted_select(self, candidates) -> str:
        """Select a prompt variant by weighted random."""
        weights = [getattr(c, 'ab_weight', 1.0) or 1.0 for c in candidates]
        total = sum(weights)
        if total <= 0:
            return candidates[0].template

        r = random.uniform(0, total)
        cumulative = 0
        for candidate, weight in zip(candidates, weights):
            cumulative += weight
            if r <= cumulative:
                return candidate.template

        return candidates[-1].template
