from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from backend.api.dependencies import ctx, require_graph
from backend.evaluation.service import export_csv, summary

router = APIRouter()


@router.post("/api/evaluation/run")
def evaluation_run(request: Request) -> dict:
    c = ctx(request)
    require_graph(c)
    try:
        with c.lock:
            return c.evaluator.run(c.snapshot())
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@router.get("/api/evaluation/results")
def evaluation_results(request: Request) -> list[dict]:
    return ctx(request).store.records("evaluations", 50)


@router.get("/api/evaluation/summary")
def evaluation_summary(request: Request) -> dict:
    return summary(ctx(request).store.records("evaluations", 50))


@router.get("/api/evaluation/results/{id}/export")
def export(id: str, request: Request, format: str = "json"):
    results = [r for r in ctx(request).store.records("evaluations", 10000) if r["id"] == id]
    if not results:
        raise HTTPException(404, "Evaluation not found")
    if format == "csv":
        return Response(
            export_csv(results[0]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="benchmark-{id}.csv"'},
        )
    if format != "json":
        raise HTTPException(422, "Format must be json or csv")
    return JSONResponse(
        results[0], headers={"Content-Disposition": f'attachment; filename="benchmark-{id}.json"'}
    )
