from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rq2.create_comparison_diagram import plot_unigram_bigram_grid
from rq2.create_top10_tfidf_figure import parse_args as parse_top10_args
from rq2.create_top5_tfidf_figure import parse_args as parse_top5_args


def _write_terms(path: Path, rows: list[tuple[str, float]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["term", "tfidf_sum"])
        writer.writerows(rows)


class TestRq2UnigramBigramGrid(unittest.TestCase):
    def test_dedicated_scripts_have_independent_configurable_defaults(self):
        top5 = parse_top5_args([])
        top10 = parse_top10_args([])

        self.assertEqual(top5.full_out.name, "top5_unigrams_bigrams_full.png")
        self.assertEqual(top5.dedup_out.name, "top5_unigrams_bigrams_dedup.png")
        self.assertEqual(top10.out.name, "top10_unigrams_bigrams_all_vs_dedup.png")
        self.assertLess(top5.fig_height, top10.fig_height)
        self.assertLess(top5.bar_step, 1.0)
        self.assertLess(top10.bar_step, 1.0)
        self.assertGreater(top5.bar_step, top5.bar_height)
        self.assertGreater(top10.bar_step, top10.bar_height)

    def test_plot_unigram_bigram_grid_writes_labeled_2x2_figure(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            left_uni = tmp_path / "left_uni.csv"
            left_bi = tmp_path / "left_bi.csv"
            right_uni = tmp_path / "right_uni.csv"
            right_bi = tmp_path / "right_bi.csv"
            out_path = tmp_path / "grid.png"

            _write_terms(left_uni, [("review", 10.0), ("research", 8.0)])
            _write_terms(left_bi, [("research findings", 5.0), ("doc structure", 4.0)])
            _write_terms(right_uni, [("agent", 7.0), ("api", 6.0)])
            _write_terms(right_bi, [("best practices", 3.0), ("ai agents", 2.0)])

            fig = plot_unigram_bigram_grid(
                left_unigrams_csv=left_uni,
                left_bigrams_csv=left_bi,
                right_unigrams_csv=right_uni,
                right_bigrams_csv=right_bi,
                out_path=out_path,
                top_k=2,
                figsize=(10, 6),
                bar_height=0.5,
                bar_step=0.7,
                row_space=0.35,
            )

            self.assertTrue(out_path.is_file())
            self.assertGreater(out_path.stat().st_size, 0)
            self.assertEqual(
                [ax.get_title(loc="left") for ax in fig.axes],
                ["Unigrams", "Unigrams", "Bigrams", "Bigrams"],
            )
            self.assertEqual(
                [ax.get_xlabel() for ax in fig.axes],
                ["", "", "Summed TF-IDF score", "Summed TF-IDF score"],
            )
            self.assertEqual(
                [text.get_text() for text in fig.texts],
                ["(a) Full corpus", "(b) Deduplicated corpus"],
            )
            self.assertLess(fig.get_figheight(), 7.0)
            self.assertLess(fig.axes[0].patches[0].get_height(), 0.62)
            for ax in fig.axes:
                bars = ax.patches
                if len(bars) > 1:
                    center_gap = bars[1].get_y() - bars[0].get_y()
                    self.assertGreaterEqual(center_gap, bars[0].get_height())
                    self.assertLess(center_gap, 1.0)


if __name__ == "__main__":
    unittest.main()
