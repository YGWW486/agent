"""GET /api/skills 内置 skill 注册测试"""

import pytest
from httpx import ASGITransport, AsyncClient

from agent.skill_dispatcher import get_dispatcher
from agent.skills.builtin import register_builtin_skills
from bridge.server import app


@pytest.fixture
def registered_dispatcher():
    d = get_dispatcher()
    register_builtin_skills(d)
    return d


def test_register_rebuild_index(registered_dispatcher):
    skill = registered_dispatcher.get_skill("rebuild_index")
    assert skill is not None
    assert skill.name == "rebuild_index"
    assert skill.category == "index"


@pytest.mark.asyncio
async def test_skills_endpoint_lists_rebuild_index(registered_dispatcher):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/skills")
    assert resp.status_code == 200
    data = resp.json()
    names = [s["name"] for s in data.get("registered_skills", [])]
    assert "rebuild_index" in names
