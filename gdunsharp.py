import tree_sitter_c_sharp
from tree_sitter import Language, Parser, Node


def print_level(node: Node, prefix: str = "", is_last: bool = False):
    print(prefix[:-1] + "-", end="")
    if node.grammar_name in ["identifier", "modifier", "comment"]:
        node_text = node.text.decode() if node.text is not None else "[None]"
        print(f"{node.grammar_name}: '{node_text}'")
    else:
        print(node.grammar_name)
    child_count = len(node.named_children)
    for child_index in range(child_count):
        child = node.named_children[child_index]
        print_level(
            child,
            ((prefix[:-2] + "  ") if is_last else (prefix)) + "| ",
            child_index >= child_count - 1,
        )


LANG_CSHARP = Language(tree_sitter_c_sharp.language())
parser = Parser(LANG_CSHARP)

tree = parser.parse(
    bytes(
        """
using Godot;

namespace Piwnica.GdFire;

public interface IMapObject
{
    Vector2 Position2d => new Vector2(GlobalPosition.X, GlobalPosition.Z);
    Vector3 GlobalPosition { get; }
}

""",
        "utf8",
    )
)

print_level(tree.root_node)
