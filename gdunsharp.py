from __future__ import annotations
from dataclasses import dataclass
import glob
import tree_sitter_c_sharp
from tree_sitter import Language, Parser, Node, Tree


class CodeIdentifier:
    def __init__(self, name: str):
        self.name = name


class CodeParam(CodeIdentifier):
    def __init__(self, name: str, type: CodeType, default_value: str):
        super().__init__(name)
        self.type = type
        self.default_value = default_value


class CodeMethod(CodeIdentifier):
    def __init__(self, name: str, type: CodeType, is_extension: bool, body_node: Node):
        super().__init__(name)
        self.type = type
        self.is_extension = is_extension
        self.generic_params: list[CodeType] = []
        self.params: list[CodeParam] = []
        self.body_node = body_node


class CodeField(CodeIdentifier):
    def __init__(self, name: str, type: CodeType):
        super().__init__(name)
        self.type = type


class CodeProperty(CodeIdentifier):
    def __init__(
        self, name: str, type: CodeType, setter: CodeMethod, getter: CodeMethod
    ):
        super().__init__(name)
        self.type = type
        self.setter = setter
        self.getter = getter


class CodeType(CodeIdentifier):
    def __init__(self, name: str):
        super().__init__(name)
        self.ancestors: list[CodeType] = []
        self.properties: list[CodeProperty] = []
        self.fields: list[CodeField] = []
        self.methods: list[CodeMethod] = []


class CodeNamespace(CodeIdentifier):
    def __init__(self, name: str, parent: CodeNamespace | None):
        super().__init__(name)
        self.parent = parent
        self.children: dict[str, CodeNamespace] = {}
        self.types: list[CodeType] = []

        if parent:
            parent.children[name] = self


class CodeDatabase:
    def __init__(self):
        self.global_namespace = CodeNamespace(name="", parent=None)


def parse_files(root_path: str) -> dict[str, Tree]:
    LANG_CSHARP = Language(tree_sitter_c_sharp.language())
    parser = Parser(LANG_CSHARP)

    paths = glob.glob(f"{root_path}/**/*.cs", recursive=True)
    trees_by_path: dict[str, Tree] = {}
    for path in paths:
        file_bytes = open(path).read().encode()
        tree = parser.parse(file_bytes)
        trees_by_path[path] = tree
    return trees_by_path


def find_node_by_grammar_name(node: Node, grammar_name: str) -> Node | None:
    if node.grammar_name == grammar_name:
        return node
    found_node: Node | None = None
    for child in node.named_children:
        found_node = find_node_by_grammar_name(child, grammar_name)
        if found_node:
            break
    return found_node


def gather_namespaces(trees_by_path: dict[str, Tree], code_database: CodeDatabase):
    for path in trees_by_path:
        tree = trees_by_path[path]
        namespace_node = find_node_by_grammar_name(
            tree.root_node, "file_scoped_namespace_declaration"
        )
        if namespace_node:
            first_child = namespace_node.named_children[0]
            if first_child.grammar_name == "qualified_name":
                assert first_child.text
                namespace_chain = first_child.text.decode().split(".")
                parent_namespace = code_database.global_namespace
                for segment_name in namespace_chain:
                    if segment_name not in parent_namespace.children:
                        ns = CodeNamespace(segment_name, parent_namespace)
                        parent_namespace = ns
                    else:
                        parent_namespace = parent_namespace.children[segment_name]


print(f"Parsing C# files...")
trees = parse_files("test_scripts/gdfire")
code_database = CodeDatabase()

print(f"Gathering namespaces...")
gather_namespaces(trees, code_database)

# Step 2: build code database of stuff in file
# Step 3: emit cpp code based on the code database
print(f"All done!")
