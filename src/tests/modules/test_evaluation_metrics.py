from src.modules.evaluation.metrics import normalize, wer


def test_normalize_folds_spelling_variants():
    assert normalize("Hume meeting mein jaana hai!") == normalize("humein meting me jana hai")


def test_wer_identical_is_zero():
    assert wer("kal ki meeting hai", "Kal ki meeting hai.") == 0.0


def test_wer_counts_substitution_and_deletion():
    assert wer("kal ki meeting hai", "kal ka meeting") == 0.5


def test_wer_empty_reference_does_not_divide_by_zero():
    assert wer("", "extra words") == 2.0
