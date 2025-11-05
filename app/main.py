from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import PlainTextResponse
from typing import Optional
import json
from .models import TransformRules
from .transform import apply_rules, extract_keys

app = FastAPI(title="WG Config Transformer", version="1.2")

@app.post("/transform", response_class=PlainTextResponse)
async def transform_config(
    file: UploadFile = File(...),
    rules_json: Optional[str] = Form(None),      # строка (как раньше)
    rules_file: Optional[UploadFile] = File(None),  # НОВОЕ: rules.json файлом
    overrides: Optional[UploadFile] = File(None)    # конфиг с ключами
):
    content = (await file.read()).decode("utf-8", errors="replace")

    # Разбираем правила: приоритет у файла, потом у строки
    rules = TransformRules()
    if rules_file is not None:
        rtxt = (await rules_file.read()).decode("utf-8", errors="replace")
        rules = TransformRules(**json.loads(rtxt))
    elif rules_json:
        rules = TransformRules(**json.loads(rules_json))

    # Ключи из overrides-конфига (если есть)
    override_keys = {}
    if overrides is not None:
        otext = (await overrides.read()).decode("utf-8", errors="replace")
        override_keys = extract_keys(otext)

    out = apply_rules(content, rules, override_keys=override_keys)
    return PlainTextResponse(out, media_type="text/plain; charset=utf-8")
