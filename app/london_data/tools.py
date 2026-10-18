"""Native Agno deterministic comparison tool; no model or database writes."""
from agno.tools import tool
from .comparison import compare


@tool
def compare_saved_observations(old_id:str,new_id:str)->dict:
    """Compare two explicitly selected saved observation IDs using frozen rules. Read-only; returns NOT_FOUND for unknown inputs. Never infer missing fields."""
    from .pipeline import repository
    repo=repository();old=repo.get('observations',old_id);new=repo.get('observations',new_id)
    if old is None or new is None:return {'status':'not_comparable','reasons':['NOT_FOUND'],'absolute_change':None,'relative_change_pct':None}
    return compare(old,new)
