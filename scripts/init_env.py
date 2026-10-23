"""Create local credentials without displaying or overwriting them."""
from pathlib import Path
import secrets

path=Path(__file__).resolve().parents[1]/'.env'
if path.exists():
    print('.env already exists; preserving it')
else:
    text=(path.parent/'.env.example').read_text()
    path.write_text(text.replace('NEO4J_PASSWORD=\n','NEO4J_PASSWORD='+secrets.token_urlsafe(24)+'\n'))
    path.chmod(0o600)
    print('Created .env with a random local Neo4j password; Ollama models must be installed separately')
