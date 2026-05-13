import logging
import time
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass
from enum import Enum

from config.settings import get_settings

logger = logging.getLogger(__name__)


class SkillStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class Skill:
    name: str
    category: str
    description: str
    parameters: Dict[str, Any]
    executor: Callable[..., Awaitable[bool]]

    async def execute(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            merged_params = {**self.parameters, **(params or {})}
            result = await self.executor(**merged_params)
            return {
                "skill": self.name,
                "success": result,
                "status": SkillStatus.SUCCESS if result else SkillStatus.FAILED
            }
        except TimeoutError:
            return {
                "skill": self.name,
                "success": False,
                "status": SkillStatus.TIMEOUT,
                "error": "Timeout"
            }
        except Exception as e:
            logger.error(f"Skill {self.name} failed: {e}")
            return {
                "skill": self.name,
                "success": False,
                "status": SkillStatus.FAILED,
                "error": str(e)
            }


class SkillDispatcher:
    def __init__(self):
        self.skills: Dict[str, Skill] = {}
        self._keyword_map: Dict[str, str] = {}
        self._stats = {
            "skills_registered": 0,
            "executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "execution_history": {}
        }

    def register(self, skill: Skill):
        self.skills[skill.name] = skill
        self._stats["skills_registered"] += 1
        if skill.name not in self._stats["execution_history"]:
            self._stats["execution_history"][skill.name] = []
        logger.info(f"Registered skill: {skill.name}")

    def register_keywords(self, skill_name: str, keywords: List[str]):
        for kw in keywords:
            self._keyword_map[kw.lower()] = skill_name

    def get_skill(self, name: str) -> Optional[Skill]:
        return self.skills.get(name)

    def list_skills(self) -> List[Dict[str, Any]]:
        skills_list = []
        for skill in self.skills.values():
            skills_list.append({
                "name": skill.name,
                "category": skill.category,
                "description": skill.description,
                "parameters": skill.parameters,
                "execution_count": len(self._stats["execution_history"].get(skill.name, []))
            })
        return skills_list

    async def execute_skill(
        self,
        name: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        skill = self.get_skill(name)
        if not skill:
            return {
                "success": False,
                "error": f"Skill not found: {name}"
            }

        start_time = time.time()
        logger.info(f"Executing skill: {name}")

        result = await skill.execute(params)
        execution_time = time.time() - start_time

        self._stats["executions"] += 1
        if result.get("success"):
            self._stats["successful_executions"] += 1
        else:
            self._stats["failed_executions"] += 1

        if name not in self._stats["execution_history"]:
            self._stats["execution_history"][name] = []
        self._stats["execution_history"][name].append({
            "timestamp": time.time(),
            "success": result.get("success"),
            "execution_time": execution_time,
            "params": params
        })

        return result

    async def select_skill(self, user_request: str) -> Optional[Skill]:
        request_lower = user_request.lower()
        for keyword, skill_name in self._keyword_map.items():
            if keyword in request_lower:
                return self.get_skill(skill_name)
        return None

    def get_skill_stats(self, skill_name: str) -> Dict[str, Any]:
        if skill_name not in self.skills:
            return {}

        history = self._stats["execution_history"].get(skill_name, [])
        if not history:
            return {
                "name": skill_name,
                "executions": 0,
                "success_rate": 0,
                "avg_execution_time": 0
            }

        successful = sum(1 for h in history if h["success"])
        success_rate = successful / len(history) * 100
        avg_time = sum(h["execution_time"] for h in history) / len(history)

        return {
            "name": skill_name,
            "executions": len(history),
            "success_rate": success_rate,
            "avg_execution_time": avg_time,
            "last_execution": history[-1] if history else None
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "skills_registered": self._stats["skills_registered"],
            "total_executions": self._stats["executions"],
            "successful_executions": self._stats["successful_executions"],
            "failed_executions": self._stats["failed_executions"],
            "skills": {
                name: self.get_skill_stats(name)
                for name in self.skills.keys()
            }
        }


_dispatcher: Optional[SkillDispatcher] = None


def get_dispatcher() -> SkillDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = SkillDispatcher()
    return _dispatcher
