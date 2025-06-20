"""
Port of https://github.com/ondrejklejch/MT-ComparEval/tree/master/libs/NGrams
"""

from collections import Counter

import regex as re


class INormalizer:
    """
    Interface for sentence normalizers.
    """

    def normalize(self, sentence: str) -> str:
        raise NotImplementedError("Subclasses must implement normalize()")


class MTEvalNormalizer(INormalizer):
    """
    MTEval-style normalizer: adds spaces around punctuation and special characters.
    """

    def normalize(self, sentence: str) -> str:
        normalized = f" {sentence} "
        # HTML entity decoding
        normalized = re.sub(r"&quot;", '"', normalized)
        normalized = re.sub(r"&amp;", "&", normalized)
        normalized = re.sub(r"&lt;", "<", normalized)
        normalized = re.sub(r"&gt;", ">", normalized)
        # Tokenize punctuation
        normalized = re.sub(r"([\{\-\~\[\-\` \-\&\(\-\+\:\-\@\/])", r" \1 ", normalized)
        # Tokenize period/comma unless adjacent to digits
        normalized = re.sub(r"([^0-9])([\.,])", r"\1 \2 ", normalized)
        normalized = re.sub(r"([\.,])([^0-9])", r" \1 \2", normalized)
        # Tokenize dash when preceded by digit
        normalized = re.sub(r"([0-9])(-)", r"\1 \2 ", normalized)
        # Collapse spaces
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = re.sub(r"^\s+", "", normalized)
        normalized = re.sub(r"\s+$", "", normalized)
        return normalized


class MTEvalInternationalNormalizer(INormalizer):
    """
    International MTEval normalizer: uses Unicode properties to tokenize punctuation and symbols.
    """

    def normalize(self, sentence: str) -> str:
        normalized = sentence
        # HTML entity decoding
        normalized = re.sub(r"&quot;", '"', normalized)
        normalized = re.sub(r"&amp;", "&", normalized)
        normalized = re.sub(r"&lt;", "<", normalized)
        normalized = re.sub(r"&gt;", ">", normalized)
        normalized = re.sub(r"&apos;", "'", normalized)
        # Tokenize punctuation (unless adjacent to digits)
        normalized = re.sub(r"(\P{N})(\p{P})", r"\1 \2 ", normalized)
        normalized = re.sub(r"(\p{P})(\P{N})", r" \1 \2", normalized)
        # Tokenize symbols
        normalized = re.sub(r"(\p{S})", r" \1 ", normalized)
        # Collapse any Unicode separators
        normalized = re.sub(r"\p{Z}+", " ", normalized)
        normalized = re.sub(r"^\p{Z}+", "", normalized)
        normalized = re.sub(r"\p{Z}+$", "", normalized)
        return normalized


class Tokenizer:
    """
    Splits sentences into tokens based on whitespace, with optional lowercasing.
    """

    def __init__(self, case_sensitive: bool = True):
        self.case_sensitive = case_sensitive

    def tokenize(self, sentence: str) -> list[str]:
        if not self.case_sensitive:
            sentence = sentence.lower()
        # Split on one or more whitespace characters
        return re.split(r"\s+", sentence.strip())


class NGramizer:
    """
    Generates all n-grams (1- to 4-grams) from a tokenized sentence.
    """

    def __init__(self, tokenizer: Tokenizer):
        self.tokenizer = tokenizer

    def get_ngrams(self, sentence: str) -> dict[int, list[str]]:
        tokens = self.tokenizer.tokenize(sentence)
        ngrams = {1: tokens[:]}
        # Build higher-order n-grams by shifting the window
        for length in range(2, 5):
            if len(tokens) < length:
                ngrams[length] = []
                continue
            tokens = tokens[1:]
            prev = ngrams[length - 1]
            ngrams[length] = [f"{prev[i]} {tokens[i]}" for i in range(len(tokens))]
        return ngrams


class ConfirmedNGramsFinder:
    """
    Finds confirmed and unconfirmed n-grams between reference and translation.
    """

    def get_confirmed_ngrams(
        self,
        reference_ngrams: dict[int, list[str]],
        translation_ngrams: dict[int, list[str]],
    ) -> dict[int, list[str]]:
        return {
            length: self._set_operation(
                reference_ngrams.get(length, []),
                translation_ngrams.get(length, []),
                min,
            )
            for length in range(1, 5)
        }

    def get_unconfirmed_ngrams(
        self,
        reference_ngrams: dict[int, list[str]],
        translation_ngrams: dict[int, list[str]],
    ) -> dict[int, list[str]]:
        return {
            length: self._set_operation(
                translation_ngrams.get(length, []),
                reference_ngrams.get(length, []),
                lambda a, b: a - b,
            )
            for length in range(1, 5)
        }

    def _set_operation(self, a: list[str], b: list[str], counter_fn) -> list[str]:
        a_counts = Counter(a)
        b_counts = Counter(b)
        result = []
        for ngram, count in a_counts.items():
            times = counter_fn(count, b_counts.get(ngram, 0))
            for _ in range(times):
                result.append(ngram)
        return result
