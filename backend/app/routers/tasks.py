from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.schemas import TaskItem, TaskListResponse
from app.services.tasks import list_vault_tasks

router = APIRouter()


@router.get("/tasks", response_model=TaskListResponse)
async def get_tasks(
    include_done: bool = False,
    _user: str = Depends(get_current_user),
) -> TaskListResponse:
    tasks = [
        TaskItem(
            path=task.path,
            line_number=task.line_number,
            text=task.text,
            completed=task.completed,
            due_date=task.due_date,
            priority=task.priority,
        )
        for task in list_vault_tasks(include_done=include_done)
    ]
    return TaskListResponse(tasks=tasks)
