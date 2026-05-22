"""Agent 节点契约 — Pydantic 模型定义"""
from pydantic import BaseModel, Field
from typing import Literal


class AcceptanceCondition(BaseModel):
    """Planner 输出的单个验收条件"""
    id: str = Field(..., description="e.g. 'AC-1'")
    description: str = Field(..., description="自然语言描述")


class Task(BaseModel):
    """Planner 输出的单个实现任务"""
    task_id: str
    description: str
    estimated_minutes: int = Field(..., le=15, description="预估工作量，≤15 分钟")
    file_scope: list[str] = Field(default_factory=list, description="涉及的文件路径")
    acceptance_conditions: list[AcceptanceCondition] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list, description="依赖的 task_id 列表")


class TaskDAG(BaseModel):
    """Planner 输出的完整任务 DAG"""
    tasks: list[Task] = Field(..., min_length=1)

    @property
    def task_count(self) -> int:
        return len(self.tasks)

    def is_complete(self, current_index: int) -> bool:
        return current_index >= len(self.tasks)

    def current_task(self, index: int) -> Task | None:
        if 0 <= index < len(self.tasks):
            return self.tasks[index]
        return None


class SelfCheckItem(BaseModel):
    """Coder 对单个验收条件的自检声明"""
    condition_id: str
    status: Literal["satisfied", "not_satisfied", "uncertain"]
    evidence: str = ""


class SelfCheckReport(BaseModel):
    """Coder 的完整自检报告"""
    items: list[SelfCheckItem]
    summary: str = ""


class FileChange(BaseModel):
    """单个文件变更"""
    path: str = Field(..., description="文件路径（相对于项目根目录）")
    content: str = Field(..., description="新文件的完整内容")
    original_content: str = Field(default="", description="修改前的内容（新建文件为空）")


class CoderOutput(BaseModel):
    """Coder 节点的结构化输出"""
    diff: str = Field(default="", description="代码变更摘要（unified diff 或完整文件内容）")
    files: list[FileChange] = Field(default_factory=list, description="所有变更的文件列表")
    self_check: SelfCheckReport


class TestCase(BaseModel):
    """Reviewer 输出的可运行测试用例"""
    name: str
    code: str = Field(..., description="可运行的测试代码（pytest 函数或 shell 脚本）")


class ReviewResult(BaseModel):
    """Reviewer 节点的结构化输出"""
    verdict: Literal["PASS", "REJECT"]
    reason: str
    test_cases: list[TestCase] = Field(..., min_length=1, description="至少一个可运行测试")
    source: Literal["reviewer", "human"] = "reviewer"


def human_reject_review(comment: str) -> ReviewResult:
    """人工审批拒绝 — 合法 ReviewResult，不计入 reviewer 修订轮次"""
    return ReviewResult(
        verdict="REJECT",
        reason=f"人工审查拒绝: {comment}",
        source="human",
        test_cases=[
            TestCase(
                name="manual_reject_placeholder",
                code=(
                    'def test_manual_reject():\n'
                    '    assert False, "人工拒绝，需修订后重新提交审批"\n'
                ),
            )
        ],
    )


# ── JSON 序列化辅助（AgentState TypedDict 字段为 str 类型，需手动序列化） ──

import json


def dag_to_json(dag: TaskDAG) -> str:
    return dag.model_dump_json(indent=2, ensure_ascii=False)


def dag_from_json(data: str | dict) -> TaskDAG:
    if isinstance(data, dict):
        return TaskDAG.model_validate(data)
    return TaskDAG.model_validate_json(data)


def coder_output_to_json(out: CoderOutput) -> str:
    return out.model_dump_json(indent=2, ensure_ascii=False)


def coder_output_from_json(data: str | dict) -> CoderOutput:
    if isinstance(data, dict):
        return CoderOutput.model_validate(data)
    return CoderOutput.model_validate_json(data)


def review_to_json(rev: ReviewResult) -> str:
    return rev.model_dump_json(indent=2, ensure_ascii=False)


def review_from_json(data: str | dict) -> ReviewResult:
    if isinstance(data, dict):
        return ReviewResult.model_validate(data)
    return ReviewResult.model_validate_json(data)
