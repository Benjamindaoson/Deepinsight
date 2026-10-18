"""Official quickstart copy: provider/config, DB path, local binding only."""
from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.os import AgentOS
from model_config import ROOT, model

db = SqliteDb(db_file=str(ROOT / 'b0/runtime-demo/agno.db'))
agent = Agent(name="Agno Assist", model=model(), db=db)
agent_os = AgentOS(agents=[agent], db=db, telemetry=False,
                   cors_allowed_origins=['http://localhost:3100', 'http://127.0.0.1:3100'])
app = agent_os.get_app()
if __name__ == "__main__":
    agent_os.serve(app="agno_assist:app", host="127.0.0.1", port=7777, reload=False)
