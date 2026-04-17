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
from functools import lru_cache
from typing import Optional, Iterable


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


_INNERMOST_PATTERN = re.compile(r"\{([^{}]*)\}")
_DEFAULT_VARIANT_POOL_LIMIT = 512


def _normalize_variant_key(value: str) -> str:
    return " ".join((value or "").split()).casefold()


@lru_cache(maxsize=256)
def _expand_variants_cached(text: str, limit: int) -> Optional[tuple[str, ...]]:
    """Expand all spintax variants up to the provided limit."""
    variants = {text}
    max_iterations = 20

    for _ in range(max_iterations):
        next_variants = set()
        changed = False

        for variant in variants:
            match = _INNERMOST_PATTERN.search(variant)
            if not match:
                next_variants.add(variant)
                continue

            changed = True
            prefix = variant[:match.start()]
            suffix = variant[match.end():]
            options = match.group(1).split("|")

            for option in options:
                next_variants.add(prefix + option + suffix)
                if len(next_variants) > limit:
                    return None

        variants = next_variants
        if not changed:
            return tuple(sorted(variants))
        if len(variants) > limit:
            return None

    return None


def expand_spintax_variants(text: str, limit: int = _DEFAULT_VARIANT_POOL_LIMIT) -> Optional[list[str]]:
    """
    Expand all unique variants when the result set is reasonably small.

    Returns None when the variant pool is larger than `limit` or expansion
    could not be completed safely.
    """
    expanded = _expand_variants_cached(text, limit)
    if expanded is None:
        return None
    return list(expanded)


def choose_unique_variant(
    text: str,
    used_values: Iterable[str],
    *,
    limit: int = _DEFAULT_VARIANT_POOL_LIMIT,
    max_random_attempts: int = 40,
) -> Optional[str]:
    """
    Choose a spintax variant that is not present in `used_values`.

    For small/medium variant pools this is exact. For very large pools it falls
    back to bounded random sampling.
    """
    used = {_normalize_variant_key(value) for value in used_values}
    expanded = expand_spintax_variants(text, limit=limit)
    if expanded is not None:
        candidates = [
            variant for variant in expanded
            if _normalize_variant_key(variant) not in used
        ]
        return random.choice(candidates) if candidates else None

    for _ in range(max_random_attempts):
        candidate = parse_spintax(text)
        if _normalize_variant_key(candidate) not in used:
            return candidate

    return None


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
