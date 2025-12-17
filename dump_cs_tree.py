import tree_sitter_c_sharp
from tree_sitter import Language, Parser, Node


def print_tree_node(node: Node, prefix: str = "", is_last: bool = False):
    if prefix:
        print(prefix[:-1] + "-", end="")
    if node.grammar_name in [
        "identifier",
        "modifier",
        "comment",
        "qualified_name",
        "integer_literal",
        "predefined_type",
        "array_rank_specifier",
    ] or (
        node.grammar_name == "accessor_declaration"
        and (
            len(node.named_children) == 0
            or node.named_children[0].grammar_name != "block"
        )
    ):
        node_text = node.text.decode() if node.text is not None else "[None]"
        print(f"{node.grammar_name}: '{node_text}'")
    else:
        print(node.grammar_name)
    child_count = len(node.named_children)
    for child_index in range(child_count):
        child = node.named_children[child_index]
        print_tree_node(
            child,
            ((prefix[:-2] + "  ") if is_last else (prefix)) + "| ",
            child_index >= child_count - 1,
        )


LANG_CSHARP = Language(tree_sitter_c_sharp.language())
parser = Parser(LANG_CSHARP)

file_bytes = (
    open("test_scripts/gdfire\Piwnica\GdFire\PLayers\Player.cs").read().encode()
)
tree = parser.parse(file_bytes)

print_tree_node(tree.root_node)
