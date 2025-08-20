import asyncio
import argparse
from evals.customer_support import CustomerSupportEval
from evals.base_eval import BaseEval
import pandas as pd
from typing import Dict, Any, Type
import dotenv

dotenv.load_dotenv()


class GenericEvaluationRunner:
    """Generic evaluation runner that can handle any BaseEval subclass"""

    def __init__(self, eval_class: Type[BaseEval], verbose: bool = False):
        self.eval_engine = eval_class(verbose=verbose)

    async def run_evaluation(self):
        """Run the complete evaluation"""
        if self.eval_engine.verbose:
            print(f"🚀 Starting {self.eval_engine.__class__.__name__} Evaluation...")
            print("📊 Creating evaluation dataset...")
        
        dataset = self.eval_engine.create_dataset()
        
        if self.eval_engine.verbose:
            print(f"✅ Dataset created: {self.eval_engine.dataset_name}")

        # Run the full evaluation
        if not self.eval_engine.verbose:
            print("🔄 Running evaluations...")
        results = await self.eval_engine.run_full_evaluation()

        # Print summary
        if not self.eval_engine.verbose:
            print(f"\nTests: {results['passed_examples']}/{results['total_examples']} passed")
        else:
            print("\n" + "=" * 60)
            print("📈 EVALUATION RESULTS")
            print("=" * 60)
            print(f"Evaluation Type: {self.eval_engine.__class__.__name__}")
            print(f"Dataset: {self.eval_engine.dataset_name}")
            print(f"Total Examples: {results['total_examples']}")
            print(f"Passed Examples: {results['passed_examples']}")
            print(f"Pass Rate: {results['pass_rate']:.3f}")
            print()

        # Show failed examples
        failed_results = [r for r in results["results"] if not r["result"].eval_passed]

        if failed_results:
            if not self.eval_engine.verbose:
                print(f"\n❌ FAILURES:")
                for result_data in failed_results:
                    result = result_data["result"]
                    inputs = result_data["inputs"]
                    original_idx = result_data["example_id"]
                    group_name = self.eval_engine.__class__.__name__.replace("Eval", "")
                    
                    # Get test name from original examples
                    examples = self.eval_engine.get_examples()
                    test_name = examples[original_idx].get("test_name", f"test_{original_idx + 1}")
                    
                    print(f"{group_name}.{test_name}:")
                    print(f"  Subject: {inputs['current_email'].subject[:50]}...")
                    if not result.trajectory_correct:
                        print(f"  - Trajectory mismatch")
                    if not result.draft_quality_good:
                        print(f"  - Draft quality failed")
                    if result.reasoning and "failed" in result.reasoning.lower():
                        print(f"  - {result.reasoning[:100]}...")
                    print()
            else:
                print("❌ FAILED EXAMPLES:")
                for i, result_data in enumerate(failed_results):
                    result = result_data["result"]
                    expected = result_data["expected_outputs"]
                    inputs = result_data["inputs"]
                    original_idx = result_data["example_id"]

                    print(f"📧 Example {original_idx + 1} (FAILED):")
                    print(f"  Email Subject: {inputs['current_email'].subject[:50]}...")
                    print(f"  Trajectory Correct: {result.trajectory_correct}")
                    print(f"  Draft Quality Good: {result.draft_quality_good}")
                    print(f"  Expected Trajectory: {expected['trajectory']}")
                    if result.reasoning:
                        print(f"  Failure Reason: {result.reasoning[:150]}...")
                    print()

        # Verbose mode shows all examples
        if self.eval_engine.verbose:
            print("\n📊 ALL EXAMPLES (VERBOSE MODE):")
            for i, result_data in enumerate(results["results"]):
                result = result_data["result"]
                expected = result_data["expected_outputs"]
                inputs = result_data["inputs"]

                status = "✅ PASSED" if result.eval_passed else "❌ FAILED"
                print(f"📧 Example {i + 1}: {status}")
                print(f"  Email Subject: {inputs['current_email'].subject[:50]}...")
                print(f"  Trajectory Correct: {result.trajectory_correct}")
                print(f"  Draft Quality Good: {result.draft_quality_good}")
                print(f"  Expected Trajectory: {expected['trajectory']}")
                if result.reasoning:
                    print(f"  Reasoning: {result.reasoning[:100]}...")
                print()

        return results

    def preview_examples(self):
        """Preview the examples without running evaluation"""
        examples = self.eval_engine.get_examples()

        print(
            f"🔍 Previewing {len(examples)} examples for {self.eval_engine.__class__.__name__}:"
        )
        print("-" * 50)

        for i, example in enumerate(examples):
            inputs = example["inputs"]
            outputs = example["outputs"]

            print(f"Example {i + 1}:")
            print(f"  📧 Subject: {inputs['current_email'].subject}")
            print(f"  👤 From: {inputs['current_email'].sender}")
            print(f"  📝 Body: {inputs['current_email'].body[:80]}...")
            print(f"  🎯 Expected Trajectory: {outputs['trajectory']}")
            print(f"  📤 Expected Response Empty: {outputs['final_draft'] == ''}")
            print(f"  📚 Past Emails Count: {len(inputs['past_emails'])}")
            print()

    def export_results_to_dataframe(self, results: Dict[str, Any]) -> pd.DataFrame:
        """Convert results to DataFrame for analysis"""
        df_data = []

        for result_data in results["results"]:
            result = result_data["result"]
            inputs = result_data["inputs"]
            expected = result_data["expected_outputs"]

            df_data.append(
                {
                    "example_id": result_data.get("example_id", 0),
                    "email_subject": inputs["current_email"].subject,
                    "email_sender": inputs["current_email"].sender,
                    "eval_passed": result.eval_passed,
                    "trajectory_correct": result.trajectory_correct,
                    "draft_quality_good": result.draft_quality_good,
                    "expected_trajectory": str(expected["trajectory"]),
                    "expected_empty_response": expected["final_draft"] == "",
                    "past_emails_count": len(inputs["past_emails"]),
                }
            )

        return pd.DataFrame(df_data)


async def run_customer_support_evaluation(verbose: bool = False):
    """Run customer support evaluation specifically"""
    runner = GenericEvaluationRunner(CustomerSupportEval, verbose=verbose)

    # Preview examples only in verbose mode
    if verbose:
        runner.preview_examples()

    # Run full evaluation
    results = await runner.run_evaluation()

    # Export results only in verbose mode
    df = runner.export_results_to_dataframe(results)
    if verbose:
        print("📊 Results DataFrame:")
        print(df.to_string(index=False))
    return results, df


async def main(verbose: bool = False):
    """Main evaluation function"""
    try:
        results, df = await run_customer_support_evaluation(verbose=verbose)

        # Print summary statistics only in verbose mode
        if verbose:
            print("\n" + "=" * 50)
            print("📊 SUMMARY STATISTICS")
            print("=" * 50)
            print(f"Overall Pass Rate: {df['eval_passed'].mean():.3f}")
            print(f"Trajectory Accuracy: {df['trajectory_correct'].mean():.3f}")
            print(f"Draft Quality Rate: {df['draft_quality_good'].mean():.3f}")

            # Show passed and failed examples
            passed_examples = df[df["eval_passed"] == True]
            failed_examples = df[df["eval_passed"] == False]

            print(f"\n🏆 Passed Examples: {len(passed_examples)}")
            if len(passed_examples) > 0:
                print("  Sample passed subjects:")
                for subject in passed_examples["email_subject"].head(3):
                    print(f"    - {subject}")

            print(f"\n⚠️ Failed Examples: {len(failed_examples)}")
            if len(failed_examples) > 0:
                print("  Sample failed subjects:")
                for subject in failed_examples["email_subject"].head(3):
                    print(f"    - {subject}")

    except Exception as e:
        print(f"❌ Error during evaluation: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generic Evaluation System")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )
    args = parser.parse_args()

    print("🚀 Generic Evaluation System")
    print("=" * 40)

    asyncio.run(main(verbose=args.verbose))
