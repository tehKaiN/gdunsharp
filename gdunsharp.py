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


class CodeType(CodeIdentifier):
    def __init__(self, name: str):
        super().__init__(name)


class CodeClass(CodeType):
    def __init__(self, name: str, kind: CodeClassKind):
        super().__init__(name)
        self.kind = kind
        self.ancestors: list[CodeClass] = []
        self.properties: list[CodeProperty] = []
        self.fields: list[CodeField] = []
        self.methods: list[CodeMethod] = []


class CodeEnumValue(CodeIdentifier):
    def __init__(self, name: str, value: str | None):
        super().__init__(name)
        self.value = value if value else ""


class CodeEnum(CodeType):
    def __init__(self, name: str):
        super().__init__(name)
        self.values: list[CodeEnumValue] = []


class CodeNamespace(CodeIdentifier):
    def __init__(self, name: str, parent: CodeNamespace | None):
        super().__init__(name)
        self.parent = parent
        self.children: dict[str, CodeNamespace] = {}
        self.types: dict[str, CodeType] = {}

        if parent:
            parent.children[name] = self

    def get_full_path(self) -> str:
        full_namespace = self.name
        parent = self.parent
        while parent and parent.name:
            full_namespace = f"{parent.name}.{full_namespace}"
            parent = parent.parent
        return full_namespace


class Codebase:
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


def get_or_create_namespace_from_node(node: Node, codebase: Codebase) -> CodeNamespace:
    first_child = node.named_children[0]
    assert first_child.grammar_name == NodeKind.QUALIFIED_NAME.value
    assert first_child.text
    namespace_chain = first_child.text.decode().split(".")
    parent_namespace = codebase.global_namespace
    for segment_name in namespace_chain:
        if segment_name not in parent_namespace.children:
            ns = CodeNamespace(segment_name, parent_namespace)
            parent_namespace = ns
        else:
            parent_namespace = parent_namespace.children[segment_name]
    return parent_namespace


def get_or_create_class_from_node(node: Node, namespace: CodeNamespace) -> CodeClass:
    match node.grammar_name:
        case NodeKind.CLASS_DECLARATION.value:
            kind = CodeClassKind.CLASS
        case NodeKind.IFACE_DECLARATION.value:
            kind = CodeClassKind.INTERFACE
        case NodeKind.STRUCT_DECLARATION.value:
            kind = CodeClassKind.STRUCT

    for child in node.named_children:
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
        found_type = namespace.types[class_name]
        assert isinstance(found_type, CodeClass)
        code_class = found_type
    return code_class


def get_or_create_enum_from_node(node: Node, namespace: CodeNamespace) -> CodeEnum:
    for child in node.named_children:
        if child.grammar_name == NodeKind.IDENTIFIER.value:
            assert child.text
            enum_name = child.text.decode()
            break

    assert enum_name
    if enum_name not in namespace.types:
        code_enum = CodeEnum(enum_name)
        namespace.types[enum_name] = code_enum
        print(f"Found enum {enum_name} in namespace {namespace.get_full_path()}")
    else:
        found_type = namespace.types[enum_name]
        assert isinstance(found_type, CodeEnum)
        code_enum = found_type
    return code_enum


def traverse_tree_level(
    parent_node: Node, codebase: Codebase, namespace_stack: list[CodeNamespace]
):
    for child_node in parent_node.named_children:
        match child_node.grammar_name:
            case NodeKind.FILE_NAMESPACE.value:
                current_namespace = get_or_create_namespace_from_node(
                    child_node, codebase
                )
                namespace_stack.append(current_namespace)
            case NodeKind.CLASS_DECLARATION.value | NodeKind.IFACE_DECLARATION.value:
                get_or_create_class_from_node(child_node, namespace_stack[-1])
            case NodeKind.ENUM_DECLARATION.value:
                get_or_create_enum_from_node(child_node, namespace_stack[-1])


def gather_namespace_and_types(trees_by_path: dict[str, Tree], codebase: Codebase):
    for path in trees_by_path:
        tree = trees_by_path[path]
        namespace_stack = [codebase.global_namespace]
        traverse_tree_level(tree.root_node, codebase, namespace_stack)


print(f"Parsing C# files...")
trees = parse_files("test_scripts/gdfire")

print(f"Gathering namespaces and types...")
codebase = Codebase()
gather_namespace_and_types(trees, codebase)

# Step 2: build code database of stuff in file
# Step 3: emit cpp code based on the code database
print(f"All done!")
