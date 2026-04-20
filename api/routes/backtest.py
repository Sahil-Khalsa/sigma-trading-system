from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

router = APIRouter(prefix="/backtest", tags=["backtest"])


class BacktestRequest(BaseModel):
    symbol: str
    start_date: str  # YYYY-MM-DD
    end_date: str

    @field_validator("symbol")
    @classmethod
    def upper(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("start_date", "end_date")
    @classmethod
    def valid_date(cls, v: str) -> str:
        from datetime import datetime
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError("Date must be YYYY-MM-DD")
        return v


@router.post("/run")
async def run_backtest(req: BacktestRequest):
    from backtest.runner import run_backtest as _run
    result = await _run(req.symbol, req.start_date, req.end_date)
    if result.error:
        raise HTTPException(status_code=422, detail=result.error)
    return result.to_dict()
