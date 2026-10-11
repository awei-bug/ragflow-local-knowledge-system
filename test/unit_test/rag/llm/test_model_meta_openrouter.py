#
#  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
from rag.llm.model_meta import OpenRouter


def _model(model_id, pricing=None):
    item = {
        "id": model_id,
        "architecture": {
            "input_modalities": ["text"],
            "output_modalities": ["text"],
        },
        "supported_parameters": [],
    }
    if pricing is not None:
        item["pricing"] = pricing
    return item


def test_openrouter_marks_free_models_from_suffix_or_zero_pricing():
    provider = OpenRouter("or-key")

    models = provider._format_model_list(
        {
            "data": [
                _model(
                    "vendor/suffix:free",
                    {"prompt": "invalid", "completion": "invalid"},
                ),
                _model(
                    "vendor/zero-priced",
                    {"prompt": "0", "completion": "0.000000"},
                ),
                _model(
                    "vendor/paid",
                    {"prompt": "0", "completion": "0.000001"},
                ),
                _model("vendor/no-pricing"),
                _model(
                    "vendor/invalid-pricing",
                    {"prompt": "free", "completion": None},
                ),
            ]
        }
    )

    assert {model["name"]: model["is_free"] for model in models} == {
        "vendor/suffix:free": True,
        "vendor/zero-priced": True,
        "vendor/paid": False,
        "vendor/no-pricing": False,
        "vendor/invalid-pricing": False,
    }
