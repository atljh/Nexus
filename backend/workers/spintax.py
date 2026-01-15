"""
Spintax Parser - Generate random text from spintax templates.

Spintax format: {option1|option2|option3}
Nested spintax is supported: {Hello|Hi {there|friend}}

Examples:
- "{Hello|Hi} {world|there}!" -> "Hello world!" or "Hi there!" etc.
- "{I|We} {love|like} {Python|coding}" -> Random combinations
"""

import re
import random
from typing import Optional


def parse_spintax(text: str) -> str:
    """
    Parse spintax text and return a random variant.

    Args:
        text: Text with spintax patterns like {option1|option2}

    Returns:
        Randomly generated text with resolved spintax
    """
    pattern = r'\{([^{}]*)\}'

    def replace_match(match: re.Match) -> str:
        options = match.group(1).split('|')
        return random.choice(options)

    # Keep replacing until no more spintax patterns (handles nested)
    max_iterations = 10  # Prevent infinite loops
    iteration = 0

    while '{' in text and '|' in text and iteration < max_iterations:
        text = re.sub(pattern, replace_match, text)
        iteration += 1

    return text


def validate_spintax(text: str) -> tuple[bool, Optional[str]]:
    """
    Validate spintax syntax.

    Args:
        text: Text to validate

    Returns:
        (is_valid, error_message)
    """
    # Check balanced braces
    open_count = text.count('{')
    close_count = text.count('}')

    if open_count != close_count:
        return False, f"Unbalanced braces: {open_count} opening, {close_count} closing"

    # Check for empty options
    if '{}' in text:
        return False, "Empty braces found"

    if '{|' in text or '|}' in text:
        return False, "Empty option in spintax"

    return True, None


def count_variants(text: str) -> int:
    """
    Count the total number of possible variants.

    Args:
        text: Spintax text

    Returns:
        Number of possible combinations
    """
    pattern = r'\{([^{}]*)\}'

    def count_options(match: re.Match) -> str:
        options = match.group(1).split('|')
        return str(len(options))

    # Replace spintax with counts
    text_with_counts = re.sub(pattern, count_options, text)

    # Find all numbers and multiply them
    numbers = re.findall(r'\d+', text_with_counts)
    if not numbers:
        return 1

    result = 1
    for num in numbers:
        result *= int(num)

    return result


def generate_samples(text: str, count: int = 5) -> list[str]:
    """
    Generate multiple sample variants from spintax.

    Args:
        text: Spintax text
        count: Number of samples to generate

    Returns:
        List of generated samples
    """
    samples = set()
    max_attempts = count * 10

    for _ in range(max_attempts):
        sample = parse_spintax(text)
        samples.add(sample)
        if len(samples) >= count:
            break

    return list(samples)[:count]


# Common comment templates with spintax
DEFAULT_COMMENT_TEMPLATES = [
    {
        "name": "Positive Reaction",
        "content": "{Wow|Amazing|Great|Awesome|Nice}! {This is|That's} {really|so|very} {cool|interesting|helpful}! {👍|🔥|❤️|👏}"
    },
    {
        "name": "Question",
        "content": "{Interesting|Cool|Nice}! {Can you|Could you|Would you} {tell|explain} more about {this|it}? {🤔|❓}"
    },
    {
        "name": "Agreement",
        "content": "{Totally|Completely|Absolutely} {agree|true}! {I think so too|Same here|Exactly}. {💯|✅|👍}"
    },
    {
        "name": "Thanks",
        "content": "{Thanks|Thank you|Thx} for {sharing|posting|this}! {Very|Really|So} {useful|helpful|informative}! {🙏|❤️|👍}"
    },
    {
        "name": "Simple",
        "content": "{Nice|Cool|Great|Good|Awesome} {post|content|stuff}! {👍|🔥|❤️|💯}"
    }
]
