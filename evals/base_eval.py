from abc import ABC, abstractmethod
from langsmith import Client
from db.schemas import CharacterProfile
from agent_orchestration.master_agent.state import Email
from agent_orchestration.master_agent.worker import Worker
from typing import List, Dict, Any
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
from typing_extensions import TypedDict, Annotated
import asyncio
import re


class Grade(TypedDict):
    """Compare the expected and actual answers and grade the actual answer."""

    reasoning: Annotated[
        str,
        ...,
        "Explain your reasoning for whether the actual response is correct or not.",
    ]
    is_correct: Annotated[
        bool,
        ...,
        "True if the student response is mostly or exactly correct, otherwise False.",
    ]


class EvaluationResult(BaseModel):
    eval_passed: bool
    trajectory_correct: bool
    draft_quality_good: bool
    reasoning: str


class BaseEval(ABC):
    """Generic evaluation class that can be extended for different evaluation types"""

    def __init__(self, dataset_name: str, verbose: bool = False):
        self.client = Client()
        self.worker = Worker()
        self.dataset_name = dataset_name
        self.grader_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
        self.verbose = verbose

    @abstractmethod
    def get_examples(self) -> List[Dict[str, Any]]:
        """Return the examples for evaluation. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def get_grader_instructions(self) -> str:
        """Return LLM-as-judge instructions specific to this evaluation type."""
        pass

    def create_dataset(self):
        """Create the evaluation dataset in LangSmith"""
        examples = self.get_examples()
        if not self.client.has_dataset(dataset_name=self.dataset_name):
            dataset = self.client.create_dataset(dataset_name=self.dataset_name)
            self.client.create_examples(dataset_id=dataset.id, examples=examples)
            return dataset
        return self.client.read_dataset(dataset_name=self.dataset_name)

    def evaluate_trajectory(
        self, expected_trajectory: List[str], actual_trajectory: List[str]
    ) -> bool:
        """Check if actual trajectory contains expected steps as a subsequence"""
        if len(expected_trajectory) > len(actual_trajectory):
            return False

        i = j = 0
        while i < len(expected_trajectory) and j < len(actual_trajectory):
            if expected_trajectory[i] == actual_trajectory[j]:
                i += 1
            j += 1

        # Return True if all expected steps were found in sequence
        return i == len(expected_trajectory)

    async def llm_as_judge_evaluate(
        self, inputs: Dict[str, Any], actual_output: str, expected_output: str
    ) -> Dict[str, Any]:
        """Use LLM as judge to check if actual and expected drafts are similar"""

        user_prompt = f"""
        Compare these two email drafts and determine if they are SIMILAR in content and meaning.

        EXPECTED DRAFT:
        {expected_output}

        ACTUAL DRAFT:
        {actual_output}

        Are these drafts similar in content, tone, and meaning? Focus on:
        - Do they convey the same main message?
        - Are the key points addressed similarly?
        - Is the overall response appropriate and equivalent?

        Respond with:
        DRAFT_QUALITY: [YES/NO]
        REASONING: [Brief explanation of similarity/differences]
        """

        response = await self.grader_llm.ainvoke(
            [{"role": "user", "content": user_prompt}]
        )

        content = response.content
        draft_quality = "DRAFT_QUALITY: YES" in content

        return {"draft_quality": draft_quality, "reasoning": content}

    async def run_evaluation(
        self, inputs: Dict[str, Any], expected_outputs: Dict[str, Any]
    ) -> EvaluationResult:
        """Run a single evaluation case"""
        character_profile = inputs["character_profile"]
        current_email = inputs["current_email"]
        past_emails = inputs["past_emails"]

        # Run the actual worker
        result = self.worker.run_agent(character_profile, current_email, past_emails)

        # Step 1: Check trajectory first
        if result.final_draft:
            actual_trajectory = ["planner", "drafter", "judge"]
        else:
            actual_trajectory = ["planner"]

        expected_trajectory = expected_outputs.get("trajectory", [])
        expected_draft = expected_outputs.get("final_draft", "")

        trajectory_correct = self.evaluate_trajectory(
            expected_trajectory, actual_trajectory
        )

        # Step 2: Check if draft is expected
        draft_expected = expected_draft != ""

        if draft_expected:
            # Use LLM judge for draft quality only when draft is expected
            llm_evaluation = await self.llm_as_judge_evaluate(
                inputs, result.final_draft or "", expected_draft
            )
            draft_quality = llm_evaluation["draft_quality"]
            reasoning = llm_evaluation["reasoning"]
        else:
            # Skip LLM evaluation when no draft is expected
            # Draft quality is good if no draft was produced when none was expected
            draft_quality = result.final_draft == "" or result.final_draft is None
            reasoning = "No draft expected - skipped LLM evaluation"

        # Step 3: Determine if evaluation passed (both trajectory and draft quality must be true)
        eval_passed = trajectory_correct and draft_quality

        # Print evaluation results only in verbose mode
        if self.verbose:
            print(f"  Trajectory Correct: {trajectory_correct}")
            print(f"  Draft Quality Good: {draft_quality}")
            print(f"  Draft Expected: {draft_expected}")
            print(f"  EVAL PASSED: {eval_passed}")
            if not eval_passed and reasoning:
                print(f"  Failure Reason: {reasoning[:200]}...")
        # In non-verbose mode, output is handled in run_full_evaluation

        return EvaluationResult(
            eval_passed=eval_passed,
            trajectory_correct=trajectory_correct,
            draft_quality_good=draft_quality,
            reasoning=reasoning,
        )

    async def run_full_evaluation(self) -> Dict[str, Any]:
        """Run evaluation on all examples"""
        examples = self.get_examples()
        results = []

        for i, example in enumerate(examples):
            if not self.verbose:
                # Get test name from example or use default
                test_name = example.get("test_name", f"test_{i + 1}")
                group_name = self.__class__.__name__.replace("Eval", "")
                print(f"{group_name}.{test_name} ", end="", flush=True)
            else:
                test_name = example.get("test_name", f"Example {i + 1}")
                print(f"Running evaluation: {test_name}")

            result = await self.run_evaluation(example["inputs"], example["outputs"])

            if not self.verbose:
                # Show result inline
                status = "✅" if result.eval_passed else "❌"
                print(f"{status}")
            else:
                print()  # Add newline for verbose mode

            results.append(
                {
                    "example_id": i,
                    "result": result,
                    "expected_outputs": example["outputs"],
                    "inputs": example["inputs"],
                }
            )

        passed_count = sum(1 for r in results if r["result"].eval_passed)

        return {
            "total_examples": len(examples),
            "passed_examples": passed_count,
            "pass_rate": passed_count / len(examples) if examples else 0.0,
            "results": results,
        }
