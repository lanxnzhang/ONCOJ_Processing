"""
oncoj.visual — visualisation utilities for ONCOJ corpus objects.

Public API
----------
ascii_tree(utt)   → str   — render an Utterance as an ASCII syntax tree
print_tree(utt)           — print ascii_tree(utt) to stdout
"""

from oncoj.visual.ascii_tree import ascii_tree, print_tree

__all__ = ["ascii_tree", "print_tree"]
