"""内置 skill 注册 — P5 仅 rebuild_index"""

from __future__ import annotations

import logging
from pathlib import Path

from agent.context import get_graph_index
from agent.skill_dispatcher import Skill, SkillDispatcher
from bridge.executor import get_executor

logger = logging.getLogger(__name__)


async def _rebuild_index_executor(graph_path: str, **_) -> bool:
    """加载 graph.json 到 GraphIndex（线程池执行阻塞 IO）"""
    index = get_graph_index()
    path = Path(graph_path)
    if not path.exists():
        raise FileNotFoundError(f"graph.json 不存在: {graph_path}")

    def _load():
        index.load(path)

    await get_executor().run(_load)
    logger.info(f"[Skill] rebuild_index loaded: {graph_path}")
    return True


def register_builtin_skills(dispatcher: SkillDispatcher) -> None:
    """在应用 lifespan 启动时调用一次"""
    if dispatcher.get_skill("rebuild_index"):
        return

    dispatcher.register(
        Skill(
            name="rebuild_index",
            category="index",
            description="加载 graphify 生成的 graph.json 到内存 GraphIndex",
            parameters={
                "graph_path": {
                    "type": "string",
                    "description": "graph.json 绝对或相对路径",
                },
            },
            executor=_rebuild_index_executor,
        )
    )
