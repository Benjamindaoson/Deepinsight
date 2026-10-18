"""B0-only native capability fixtures; no business logic or substitute runtime.

Patterns: Agno v2.9.0 cookbook/00_quickstart/sequential_workflow.py,
03_teams/01_quickstart/03_delegate_to_all_members.py,
02_agents/16_skills/basic_skills.py and 05_agent_os/12_scheduler.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'b0/runtime-demo'))
from model_config import model
from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.os import AgentOS
from agno.skills import LocalSkills, Skills
from agno.team import Team, TeamMode
from agno.workflow import Step, Workflow

db = SqliteDb(id='b0-sqlite', db_file=str(ROOT / 'b0/runtime-demo/native.db'))

def add_numbers(a: int, b: int) -> int:
    """Add two integers and return their sum."""
    result = a + b
    with (ROOT / 'b0/evidence/logs/tool-invocations.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps({'time': time.time(), 'tool': 'add_numbers', 'a': a, 'b': b, 'result': result}) + '\n')
    return result

agent = Agent(id='b0-agent', name='B0 Agent', model=model(), db=db,
              tools=[add_numbers], add_history_to_context=True, num_history_runs=5,
              store_events=True, telemetry=False,
              instructions=['Keep replies under 60 words. Use add_numbers whenever explicitly requested.'])

draft = Agent(name='Draft Agent', model=model(), telemetry=False,
              instructions=['Draft a short explanation from the request in under 40 words. Preserve any marker.'])
review = Agent(name='Review Agent', model=model(), telemetry=False,
               instructions=['Review and improve the previous step output. Preserve its marker. Use under 40 words.'])
workflow = Workflow(id='b0-workflow', name='B0 Sequential Workflow', db=db,
                    steps=[Step(name='Draft', agent=draft), Step(name='Review', agent=review)],
                    store_events=True, telemetry=False)

member_a = Agent(id='b0-explainer', name='Explainer', role='Explain advantages of Python.',
                 model=model(), instructions=['Give two concrete advantages in under 40 words.'], telemetry=False)
member_b = Agent(id='b0-reviewer', name='Reviewer', role='Review and summarize the topic.',
                 model=model(), instructions=['Summarize the main tradeoff in under 30 words.'], telemetry=False)
team = Team(id='b0-team', name='B0 Review Team', model=model(), members=[member_a, member_b],
            mode=TeamMode.broadcast, db=db, show_members_responses=True,
            store_member_responses=True, store_events=True, telemetry=False,
            instructions=['Involve both members and synthesize their perspectives in under 60 words.'])

skills = Skills(loaders=[LocalSkills(str(ROOT / 'upstream/agno/cookbook/02_agents/16_skills/sample_skills'))])
skills_agent = Agent(id='b0-skills', name='B0 Native Skills', model=model(), db=db, skills=skills,
                     store_events=True, telemetry=False,
                     instructions=['For code review first call get_skill_instructions for code-review. Keep final answer under 60 words.'])

agent_os = AgentOS(id='deepinsight-b0', agents=[agent, skills_agent], teams=[team],
                   workflows=[workflow], db=db, telemetry=False, tracing=True,
                   cors_allowed_origins=['http://localhost:3100', 'http://127.0.0.1:3100'],
                   scheduler=True, scheduler_poll_interval=5,
                   scheduler_base_url='http://127.0.0.1:7777')
app = agent_os.get_app()
if __name__ == '__main__':
    agent_os.serve(app=app, host='127.0.0.1', port=7777, reload=False)
