import pytest
from app.services.test_runner import run_length_check, run_keyword_check, run_test


class TestLengthCheck:
    def test_pass_within_range(self):
        output = " ".join(["word"] * 50)
        result = run_length_check(output)
        assert result.status == "passed"
        assert 0.7 <= result.score <= 1.0

    def test_fail_too_short(self):
        result = run_length_check("too short")
        assert result.status == "failed"
        assert result.score < 1.0

    def test_fail_too_long(self):
        output = " ".join(["word"] * 250)
        result = run_length_check(output)
        assert result.status == "failed"
        assert result.score < 1.0

    def test_boundary_exactly_10_words(self):
        output = " ".join(["word"] * 10)
        result = run_length_check(output)
        assert result.status == "passed"

    def test_boundary_exactly_200_words(self):
        output = " ".join(["word"] * 200)
        result = run_length_check(output)
        assert result.status == "passed"

    def test_score_proportional_when_too_short(self):
        result = run_length_check("one")  # 1 word, min is 10
        assert result.score == round(1 / 10, 2)

    def test_score_proportional_when_too_long(self):
        output = " ".join(["word"] * 400)  # 400 words, max is 200
        result = run_length_check(output)
        assert result.score == round(200 / 400, 2)


class TestKeywordCheck:
    def test_pass_all_keywords_present(self):
        result = run_keyword_check(
            "Python lists are mutable sequences", "explain python lists"
        )
        assert result.status == "passed"
        assert result.score == 1.0

    def test_fail_no_keywords_present(self):
        result = run_keyword_check(
            "completely unrelated output about bananas",
            "explain quantum entanglement feynman diagrams",
        )
        assert result.status == "failed"
        assert result.score == 0.0

    def test_pass_at_50_percent(self):
        # keywords: "quantum", "computing" (2 words > 3 chars, not stop words)
        result = run_keyword_check("quantum bananas", "quantum computing")
        assert result.status == "passed"
        assert result.score == 0.5

    def test_fail_below_50_percent(self):
        # keywords: "quantum", "entanglement", "diagrams" — only 1 of 3 present
        result = run_keyword_check("quantum bananas", "quantum entanglement diagrams")
        assert result.status == "failed"
        assert result.score == round(1 / 3, 2)

    def test_stop_words_ignored(self):
        # "what", "is", "the" are stop words; "meaning" and "life" are keywords
        result = run_keyword_check("meaning of life", "what is the meaning of life")
        assert result.status == "passed"

    def test_empty_keywords_passes_with_neutral_score(self):
        # all words are stop words or <= 3 chars
        result = run_keyword_check("anything", "what is it")
        assert result.status == "passed"
        assert result.score == 0.5

    def test_case_insensitive(self):
        result = run_keyword_check("Python is great", "explain Python")
        assert result.status == "passed"


class TestRunTest:
    def test_dispatches_length(self):
        result = run_test("length", " ".join(["word"] * 50))
        assert result.status == "passed"

    def test_dispatches_keyword(self):
        result = run_test("keyword", "python lists", "explain python lists")
        assert result.status == "passed"

    def test_raises_on_unknown_type(self):
        with pytest.raises(ValueError, match="Unknown test_type"):
            run_test("unknown", "output")
