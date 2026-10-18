# Snapshot of https://docs.agno.com/agent-os/run-your-os retrieved 2026-10-17.
# Reference only. The runnable copy is agno_assist.py.
from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.anthropic import Claude
from agno.os import AgentOS

db = SqliteDb(db_file="agno.db")
agent = Agent(name="Agno Assist", model=Claude(id="claude-sonnet-4-5"), db=db)
agent_os = AgentOS(agents=[agent], db=db)
app = agent_os.get_app()
if __name__ == "__main__":
    agent_os.serve(app="agno_assist:app", reload=True)
