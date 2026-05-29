import io
import tempfile
import unittest
import zipfile
from pathlib import Path

import prism_session
from prism_engine import (
    Segment,
    SimulatedResponse,
    SurveyQuestion,
    _aggregate_responses,
    _has_terminal_punctuation,
    _is_transient_llm_error,
    _is_incomplete_free_text,
    _max_tokens_for_question,
    _parse_response,
    _respondent_variation,
    analyze_run_quality,
    configure_models,
    estimate_request_count,
    get_model_config,
)
from prism_session import (
    import_zip,
    load_responses,
    question_from_dict,
    question_to_dict,
    response_from_dict,
    response_to_dict,
    save_responses,
)


class PrismCoreTests(unittest.TestCase):
    def test_respondent_variation_changes_across_replicates(self):
        first = _respondent_variation(0)
        second = _respondent_variation(1)

        self.assertNotEqual(first, second)
        self.assertIn("budget pressure", first)
        self.assertIn("tech comfort", second)

    def test_parse_multi_select_letters_only(self):
        question = SurveyQuestion(
            id="q_drivers",
            text="Pick drivers",
            type="multi_select",
            options=["Price", "Availability", "Convenience"],
        )

        self.assertEqual(
            _parse_response(question, "A, C"),
            ["Price", "Convenience"],
        )

    def test_aggregate_responses_computes_sdb_gap_and_multi_select_rates(self):
        segments = [
            Segment(
                name="Urban Couples",
                description="You are an urban couple.",
                weight=1.0,
                rationale="Target segment",
            )
        ]
        questions = [
            SurveyQuestion(
                id="q_behavior_anon",
                text="How much do costs delay childbearing?",
                type="likert5",
                condition="anonymous",
            ),
            SurveyQuestion(
                id="q_behavior_named",
                text="How much do costs delay childbearing?",
                type="likert5",
                condition="named",
            ),
            SurveyQuestion(
                id="q_drivers",
                text="Select barriers",
                type="multi_select",
                options=["Housing", "Childcare"],
            ),
        ]
        responses = [
            SimulatedResponse("Urban Couples", "", "q_behavior_anon", "5", 5),
            SimulatedResponse("Urban Couples", "", "q_behavior_anon", "4", 4),
            SimulatedResponse("Urban Couples", "", "q_behavior_named", "3", 3),
            SimulatedResponse("Urban Couples", "", "q_behavior_named", "2", 2),
            SimulatedResponse("Urban Couples", "", "q_drivers", "A,B", ["Housing", "Childcare"]),
            SimulatedResponse("Urban Couples", "", "q_drivers", "A", ["Housing"]),
        ]

        result = _aggregate_responses(responses, segments, questions)[0]

        self.assertEqual(result.question_summaries["q_behavior_anon"]["mean"], 4.5)
        self.assertEqual(result.question_summaries["q_behavior_named"]["mean"], 2.5)
        self.assertEqual(result.question_summaries["__sdb_gaps__"]["q_behavior"], 2.0)
        self.assertEqual(result.question_summaries["q_drivers"]["rates"]["Housing"], 100.0)
        self.assertEqual(result.question_summaries["q_drivers"]["rates"]["Childcare"], 50.0)

    def test_question_serialization_preserves_ssr_fields(self):
        question = SurveyQuestion(
            id="q1",
            text="Do you support this?",
            type="likert5",
            scale_label="1=No, 5=Yes",
            use_ssr=True,
            anchors=["a", "b", "c", "d", "e"],
        )

        restored = question_from_dict(question_to_dict(question))

        self.assertTrue(restored.use_ssr)
        self.assertEqual(restored.anchors, ["a", "b", "c", "d", "e"])

    def test_response_serialization_roundtrip(self):
        response = SimulatedResponse(
            segment_name="Segment A",
            persona_detail="Persona",
            question_id="q1",
            raw_response="I agree.",
            parsed_value=4.2,
            pmf=[0.0, 0.1, 0.2, 0.3, 0.4],
            finish_reason="stop",
        )

        restored = response_from_dict(response_to_dict(response))

        self.assertEqual(restored.segment_name, response.segment_name)
        self.assertEqual(restored.parsed_value, response.parsed_value)
        self.assertEqual(restored.pmf, response.pmf)
        self.assertEqual(restored.finish_reason, response.finish_reason)

    def test_save_and_load_responses_uses_run_directory(self):
        original_runs_dir = prism_session.RUNS_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                prism_session.RUNS_DIR = Path(tmp)
                response = SimulatedResponse("Segment A", "", "q1", "5", 5)

                save_responses("run_1", [response])
                restored = load_responses("run_1")

                self.assertEqual(len(restored), 1)
                self.assertEqual(restored[0].segment_name, "Segment A")
                self.assertEqual(restored[0].parsed_value, 5)
        finally:
            prism_session.RUNS_DIR = original_runs_dir

    def test_import_zip_rejects_path_traversal(self):
        original_runs_dir = prism_session.RUNS_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                prism_session.RUNS_DIR = Path(tmp)
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w") as zf:
                    zf.writestr("../evil.txt", "nope")

                with self.assertRaises(ValueError):
                    import_zip(buf.getvalue())
        finally:
            prism_session.RUNS_DIR = original_runs_dir

    def test_configure_models_updates_runtime_config(self):
        original = get_model_config()
        try:
            configure_models("agent-test", "sim-test", "embed-test", "english", 123)
            self.assertEqual(get_model_config()["agent_model"], "agent-test")
            self.assertEqual(get_model_config()["sim_model"], "sim-test")
            self.assertEqual(get_model_config()["embed_model"], "embed-test")
            self.assertEqual(get_model_config()["response_language"], "english")
            self.assertEqual(get_model_config()["requests_per_minute"], "123.0")
        finally:
            configure_models(
                original["agent_model"],
                original["sim_model"],
                original["embed_model"],
                original["response_language"],
                original["requests_per_minute"],
            )

    def test_estimate_request_count_includes_ssr_embeddings(self):
        segments = [Segment("A", "persona", 1.0, "reason")]
        questions = [
            SurveyQuestion("q1", "Likert", "likert5", use_ssr=True),
            SurveyQuestion("q2", "Open", "open"),
        ]

        estimate = estimate_request_count(segments, questions, 3)

        self.assertEqual(estimate["simulation_calls"], 6)
        self.assertEqual(estimate["ssr_response_embedding_calls"], 3)
        self.assertEqual(estimate["ssr_anchor_embedding_calls"], 5)
        self.assertEqual(estimate["agent_calls"], 1)
        self.assertEqual(estimate["total_requests"], 15)

    def test_analyze_run_quality_flags_duplicates_and_missing(self):
        segments = [Segment("A", "persona", 1.0, "reason")]
        questions = [SurveyQuestion("q1", "Likert", "likert5")]
        responses = [
            SimulatedResponse("A", "", "q1", "2", 2),
            SimulatedResponse("A", "", "q1", "2", 2),
        ]

        quality = analyze_run_quality(responses, segments, questions, 3)

        self.assertEqual(quality["expected_responses"], 3)
        self.assertEqual(quality["actual_responses"], 2)
        self.assertEqual(quality["duplicate_cell_rate"], 1.0)
        self.assertEqual(quality["all_same_likert_rate"], 1.0)
        self.assertEqual(quality["missing_cells"][0]["actual"], 2)

    def test_type_specific_max_tokens(self):
        self.assertEqual(_max_tokens_for_question(SurveyQuestion("q", "Likert", "likert5")), 16)
        self.assertEqual(_max_tokens_for_question(SurveyQuestion("q", "Binary", "binary")), 8)
        self.assertEqual(_max_tokens_for_question(SurveyQuestion("q", "WTP", "wtp")), 16)
        self.assertEqual(_max_tokens_for_question(SurveyQuestion("q", "Multi", "multi_select")), 64)
        self.assertEqual(
            _max_tokens_for_question(SurveyQuestion("q", "SSR", "likert5", use_ssr=True)),
            1024,
        )
        self.assertEqual(_max_tokens_for_question(SurveyQuestion("q", "Open", "open")), 1024)

    def test_free_text_completion_heuristic(self):
        self.assertTrue(_has_terminal_punctuation("This is complete."))
        self.assertTrue(_is_incomplete_free_text("Honestly, for me, if there's"))
        self.assertFalse(
            _is_incomplete_free_text(
                "I worry about the monthly subscription cost more than the rebate itself."
            )
        )

    def test_transient_llm_error_detection_includes_high_demand_503(self):
        class ServiceUnavailableError(Exception):
            pass

        error = ServiceUnavailableError(
            "GeminiException - 503 UNAVAILABLE: This model is currently experiencing high demand."
        )

        self.assertTrue(_is_transient_llm_error(error))
        self.assertFalse(_is_transient_llm_error(ValueError("bad json shape")))


if __name__ == "__main__":
    unittest.main()
