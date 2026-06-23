"""
Evaluation pipeline: loads golden_dataset.jsonl, runs each question through
the RAG pipeline, scores with a local LLM judge, and logs to Langfuse.
A question-trap failure is a blocking failure (exit code 1).
"""
import json
import sys
from pathlib import Path

import ollama
from langfuse import Langfuse

from config.settings import settings
from src.generation.answer import answer

_GOLDEN = Path(__file__).parent / "golden_dataset.jsonl"

_JUDGE_PROMPT = """\
Tu es un évaluateur rigoureux d'un système RAG sur les statistiques artistiques françaises.

Question posée : {question}

Comportement attendu : {expected_behavior}

Réponse du système :
{response}

Évalue si la réponse respecte le comportement attendu.
Réponds UNIQUEMENT avec un JSON : {{"pass": true/false, "reason": "..."}}
"""


def judge(question: str, expected_behavior: str, response: str) -> dict:
    prompt = _JUDGE_PROMPT.format(
        question=question,
        expected_behavior=expected_behavior,
        response=response,
    )
    raw = ollama.chat(
        model=settings.ollama_llm_model,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0},
    )["message"]["content"]

    try:
        import re
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        return json.loads(m.group()) if m else {"pass": False, "reason": raw}
    except Exception:
        return {"pass": False, "reason": raw}


def run_evaluation() -> None:
    lf = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )

    dataset_name = "golden-artistes-auteurs"
    items = [json.loads(l) for l in _GOLDEN.read_text().splitlines() if l.strip()]

    # Create dataset in Langfuse (idempotent)
    try:
        lf.create_dataset(name=dataset_name)
    except Exception:
        pass

    failures: list[str] = []

    for item in items:
        question = item["question"]
        expected = item["expected_behavior"]

        # Create dataset item
        try:
            lf.create_dataset_item(
                dataset_name=dataset_name,
                input={"question": question},
                expected_output={"expected_behavior": expected},
            )
        except Exception:
            pass

        # Run pipeline
        result = answer(question)
        response_text = result["answer"]

        # Score with local LLM judge
        verdict = judge(question, expected, response_text)
        score = 1.0 if verdict.get("pass") else 0.0

        trace = lf.trace(
            name="eval_run",
            input={"question": question},
            output={"answer": response_text},
            metadata={"expected_behavior": expected},
        )
        lf.score(
            trace_id=trace.id,
            name="trap_pass",
            value=score,
            comment=verdict.get("reason", ""),
        )

        if not verdict.get("pass"):
            failures.append(f"FAIL — {question}\n  Raison : {verdict.get('reason')}")
            print(f"✗ {question}")
        else:
            print(f"✓ {question}")

    lf.flush()

    if failures:
        print("\n=== ÉCHECS BLOQUANTS ===")
        for f in failures:
            print(f)
        sys.exit(1)


if __name__ == "__main__":
    run_evaluation()
