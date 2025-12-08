from __future__ import annotations
import glob
from enum import Enum
import tree_sitter_c_sharp
from tree_sitter import Language, Parser, Node, Tree


class NodeKind(Enum):
    CLASS_DECLARATION = "class_declaration"
    IFACE_DECLARATION = "interface_declaration"
    STRUCT_DECLARATION = "struct_declaration"
    ENUM_DECLARATION = "enum_declaration"
    QUALIFIED_NAME = "qualified_name"
    FILE_NAMESPACE = "file_scoped_namespace_declaration"
    IDENTIFIER = "identifier"
    LITERAL_INT = "integer_literal"


class CodeIdentifier:
    def __init__(self, name: str):
        self.name = name


class CodeParam(CodeIdentifier):
    def __init__(self, name: str, type: CodeClass, default_value: str):
        super().__init__(name)
        self.type = type
        self.default_value = default_value


class CodeMethod(CodeIdentifier):
    def __init__(self, name: str, type: CodeClass, is_extension: bool, body_node: Node):
        super().__init__(name)
        self.type = type
        self.is_extension = is_extension
        self.generic_params: list[CodeClass] = []
        self.params: list[CodeParam] = []
        self.body_node = body_node


class CodeField(CodeIdentifier):
    def __init__(self, name: str, type: CodeClass):
        super().__init__(name)
        self.type = type


class CodeProperty(CodeIdentifier):
    def __init__(
        self, name: str, type: CodeClass, setter: CodeMethod, getter: CodeMethod
    ):
        super().__init__(name)
        self.type = type
        self.setter = setter
        self.getter = getter


class CodeClassKind(Enum):
    CLASS = 1
    STRUCT = 2
    INTERFACE = 3


class CodeClass(CodeIdentifier):
    def __init__(self, name: str, kind: CodeClassKind):
        super().__init__(name)
        self.kind = kind
        self.ancestors: list[CodeClass] = []
        self.properties: list[CodeProperty] = []
        self.fields: list[CodeField] = []
        self.methods: list[CodeMethod] = []


class CodeNamespace(CodeIdentifier):
    def __init__(self, name: str, parent: CodeNamespace | None):
        super().__init__(name)
        self.parent = parent
        self.children: dict[str, CodeNamespace] = {}
        self.types: dict[str, CodeClass] = {}

        if parent:
            parent.children[name] = self

    def get_full_path(self) -> str:
        full_namespace = self.name
        parent = self.parent
        while parent and parent.name:
            full_namespace = f"{parent.name}.{full_namespace}"
            parent = parent.parent
        return full_namespace


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


def get_or_create_namespace_from_node(
    namespace_node: Node, code_database: CodeDatabase
) -> CodeNamespace:
    first_child = namespace_node.named_children[0]
    assert first_child.grammar_name == NodeKind.QUALIFIED_NAME.value
    assert first_child.text
    namespace_chain = first_child.text.decode().split(".")
    parent_namespace = code_database.global_namespace
    for segment_name in namespace_chain:
        if segment_name not in parent_namespace.children:
            ns = CodeNamespace(segment_name, parent_namespace)
            parent_namespace = ns
        else:
            parent_namespace = parent_namespace.children[segment_name]
    return parent_namespace


def get_or_create_class_from_node(
    class_node: Node, code_database: CodeDatabase, namespace: CodeNamespace
) -> CodeClass:
    match class_node.grammar_name:
        case NodeKind.CLASS_DECLARATION.value:
            kind = CodeClassKind.CLASS
        case NodeKind.IFACE_DECLARATION.value:
            kind = CodeClassKind.INTERFACE
        case NodeKind.STRUCT_DECLARATION.value:
            kind = CodeClassKind.STRUCT

    for child in class_node.named_children:
        if child.grammar_name == NodeKind.IDENTIFIER.value:
            assert child.text
            class_name = child.text.decode()
            break

    assert class_name
    if class_name not in namespace.types:
        code_class = CodeClass(class_name, kind)
        namespace.types[class_name] = code_class
        print(
            f"Found {kind.name.lower()} {class_name} in namespace {namespace.get_full_path()}"
        )
    else:
        code_class = namespace.types[class_name]
    return code_class


def traverse_tree_level(
    parent_node: Node, code_database: CodeDatabase, namespace_stack: list[CodeNamespace]
):
    for child_node in parent_node.named_children:
        match child_node.grammar_name:
            case NodeKind.FILE_NAMESPACE.value:
                current_namespace = get_or_create_namespace_from_node(
                    child_node, code_database
                )
                namespace_stack.append(current_namespace)
            case NodeKind.CLASS_DECLARATION.value | NodeKind.IFACE_DECLARATION.value:
                get_or_create_class_from_node(
                    child_node, code_database, namespace_stack[-1]
                )


def gather_namespace_and_types(
    trees_by_path: dict[str, Tree], code_database: CodeDatabase
):
    for path in trees_by_path:
        tree = trees_by_path[path]
        namespace_stack = [code_database.global_namespace]
        traverse_tree_level(tree.root_node, code_database, namespace_stack)


print(f"Parsing C# files...")
trees = parse_files("test_scripts/gdfire")
code_database = CodeDatabase()

print(f"Gathering namespaces and types...")
gather_namespace_and_types(trees, code_database)

# Step 2: build code database of stuff in file
# Step 3: emit cpp code based on the code database
print(f"All done!")
