from dataclasses import dataclass

STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "about", "what",
    "how", "why", "when", "where", "who", "which", "and", "or", "but",
    "if", "so", "yet", "both", "not", "it", "its", "this", "that", "me",
    "my", "we", "our", "you", "your", "i", "simply", "please", "explain",
}


@dataclass
class TestOutcome:
    status: str   # "passed" | "failed"
    score: float


def run_length_check(output: str, input_prompt: str = "") -> TestOutcome:
    word_count = len(output.split())
    MIN_WORDS, MAX_WORDS = 10, 200

    if word_count < MIN_WORDS:
        score = round(word_count / MIN_WORDS, 2)
    elif word_count > MAX_WORDS:
        score = round(MAX_WORDS / word_count, 2)
    else:
        score = round(0.7 + 0.3 * (word_count - MIN_WORDS) / (MAX_WORDS - MIN_WORDS), 2)

    status = "passed" if MIN_WORDS <= word_count <= MAX_WORDS else "failed"
    return TestOutcome(status=status, score=score)


def run_keyword_check(output: str, input_prompt: str) -> TestOutcome:
    keywords = [
        word.lower().strip("?.,!")
        for word in input_prompt.split()
        if len(word) > 3 and word.lower() not in STOP_WORDS
    ]

    if not keywords:
        # nothing meaningful to check — pass with neutral score
        return TestOutcome(status="passed", score=0.5)

    output_lower = output.lower()
    matched = [kw for kw in keywords if kw in output_lower]
    score = round(len(matched) / len(keywords), 2)
    status = "passed" if score >= 0.5 else "failed"
    return TestOutcome(status=status, score=score)


def run_test(test_type: str, output: str, input_prompt: str = "") -> TestOutcome:
    runners = {
        "length": run_length_check,
        "keyword": run_keyword_check,
    }
    runner = runners.get(test_type)
    if not runner:
        raise ValueError(f"Unknown test_type: '{test_type}'")
    return runner(output, input_prompt)
