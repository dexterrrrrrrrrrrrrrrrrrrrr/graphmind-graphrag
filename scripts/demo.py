"""Real Ollama HTTP acceptance. Never accepts legacy/demo extraction as live validation."""
import argparse
import json
import time
from pathlib import Path

import httpx

parser = argparse.ArgumentParser()
parser.add_argument('--api', default='http://127.0.0.1:8000/api')
parser.add_argument('--reprocess', action='store_true', help='Explicitly re-ingest existing demo documents with configured Ollama')
parser.add_argument('--output', default='.data/ollama-acceptance')
args = parser.parse_args()
with httpx.Client(base_url=args.api, timeout=1800, trust_env=False) as client:
    state = client.get('/ollama/status')
    state.raise_for_status()
    if not state.json()['ready']:
        raise SystemExit('Live validation blocked: ' + state.json()['message'])
    ids = []
    for file in sorted((Path(__file__).resolve().parents[1] / 'datasets/demo').glob('*.txt')):
        response = client.post('/documents/upload', files={'file': (file.name, file.read_bytes(), 'text/plain')})
        if response.status_code == 409:
            id = response.json()['error']['document_id']
            doc = client.get('/documents/' + id).json()
            if args.reprocess:
                queued = client.post('/documents/' + id + '/reprocess')
                queued.raise_for_status()
            elif doc['processing_metadata'].get('pipeline_version') != 'graphmind-ollama-v2':
                raise SystemExit('Existing demo has legacy extraction. Use --reprocess to authorize re-ingestion; existing data is preserved.')
        else:
            response.raise_for_status()
            id = response.json()['id']
        ids.append(id)
    deadline = time.monotonic() + 1800
    while time.monotonic() < deadline:
        docs = [client.get('/documents/' + id).json() for id in ids]
        if any(d['status'] == 'failed' for d in docs):
            raise SystemExit('Ingestion failed: ' + str([(d['name'], d['error']) for d in docs if d['status'] == 'failed']))
        if all(d['status'] == 'ready' for d in docs):
            break
        time.sleep(2)
    else:
        raise SystemExit('Ingestion timeout; inspect /api/documents status')
    assert all(d['processing_metadata'].get('pipeline_version') == 'graphmind-ollama-v2' for d in docs)
    question = "Which organization is indirectly connected to Rahul Sharma through his company's acquisition and subsequent partnership?"
    response = client.post('/query/compare', json={'question': question})
    response.raise_for_status()
    comparison = response.json()
    result = comparison['hybrid']
    assert result['provider'] == 'ollama' and 'MedCore' in result['answer'], result
    assert {c['document_id'] for c in result['citations']} == set(ids), result
    assert any([n['name'] for n in p['nodes']] == ['Rahul Sharma', 'AlphaTech', 'DataVision', 'MedCore']
               and len(p['edges']) == 3 for p in result['paths']), result
    assert comparison['vector']['paths'] == [] and comparison['vector']['fallback'] is None
    response = client.post('/evaluation/run')
    response.raise_for_status()
    benchmark = response.json()
    assert all(r['status'] == 'completed' for r in benchmark['rows']), benchmark
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix('.json').write_text(json.dumps({'models': state.json(), 'documents': docs,
        'comparison': comparison, 'benchmark': benchmark}, indent=2))
    csv = client.get('/evaluation/results/' + benchmark['id'] + '/export?format=csv')
    csv.raise_for_status()
    output.with_suffix('.csv').write_text(csv.text)
    print('PASS: real Ollama extraction, local embeddings, MedCore, three document citations, actual Neo4j three-hop path, vector comparison and measured benchmark.')
    print('Results:', output.with_suffix('.json'), output.with_suffix('.csv'))
